"""Cloudflare Access gate. Access signs in the visitor (email one-time code) and forwards a signed token on every request.
The origin must check it, otherwise the plain onrender.com address would bypass Access altogether."""
import jwt
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from jwt import PyJWKClient

from app.core.config import settings

# Reachable without Access: Render's health checks, and the endpoints Bolna calls (it cannot type a code).
# Those are protected by their own bearer secret and by verifying every call with Bolna.
OPEN_PATHS = ("/healthz", "/readyz", "/api/v1/voice/")
_client: PyJWKClient | None = None


def enabled() -> bool:
    return bool(settings.access_team_domain and settings.access_aud)


def _jwks() -> PyJWKClient:
    global _client
    if _client is None:
        _client = PyJWKClient(f"https://{settings.access_team_domain}/cdn-cgi/access/certs", cache_keys=True, lifespan=3600)
    return _client


def valid(token: str) -> bool:
    try:
        key = _jwks().get_signing_key_from_jwt(token)
        jwt.decode(token, key.key, algorithms=["RS256"], audience=settings.access_aud, issuer=f"https://{settings.access_team_domain}")
        return True
    except Exception:  # bad signature, wrong audience, expired, or the certs could not be fetched: all mean no access
        return False


async def gate(request: Request, call_next):
    path = request.url.path
    if not enabled() or any(path == p or path.startswith(p) for p in OPEN_PATHS):
        return await call_next(request)
    token = request.headers.get("cf-access-jwt-assertion", "")
    if token and await run_in_threadpool(valid, token):
        return await call_next(request)
    where = settings.console_url or settings.public_base_url
    return JSONResponse({"detail": f"Sign in through {where} to use this app."}, status_code=403)
