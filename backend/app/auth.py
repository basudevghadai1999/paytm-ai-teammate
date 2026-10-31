"""Google sign-in for the whole site. Only Google accounts listed in ALLOWED_EMAILS get a session.

Authorization-code flow with an ID token check (signature, audience, issuer, nonce, verified email). The session is a signed,
HttpOnly cookie; the allowlist is re-checked on every request, so removing an email locks that person out at once.
Can run alongside the Cloudflare Access gate (app/access.py): a valid Access token or a valid session is enough."""
import hmac
import html
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jwt import PyJWKClient

from app import access
from app.core.config import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
SESSION, STATE = "pt_session", "pt_state"
SESSION_TTL, STATE_TTL = 8 * 3600, 600
OPEN_PATHS = access.OPEN_PATHS + ("/auth/",)  # the sign-in routes themselves must be reachable
router = APIRouter(prefix="/auth")
_certs: PyJWKClient | None = None


def allowed() -> set[str]:
    return {e.strip().lower() for e in settings.allowed_emails.split(",") if e.strip()}


def enabled() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and allowed())


def _base() -> str:
    return (settings.console_url or settings.public_base_url).rstrip("/")


def _secure() -> bool:
    return _base().startswith("https://")


def _sign(payload: dict, ttl: int) -> str:
    return jwt.encode({**payload, "exp": int(time.time()) + ttl}, settings.session_secret, algorithm="HS256")


def _read(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return jwt.decode(token, settings.session_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def session_email(request: Request) -> str | None:
    p = _read(request.cookies.get(SESSION))
    email = str((p or {}).get("email") or "").lower()
    return email if email and email in allowed() else None


def exchange_code(code: str) -> str:
    r = httpx.post(TOKEN_URL, timeout=10, data={
        "code": code, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
        "redirect_uri": f"{_base()}/auth/callback", "grant_type": "authorization_code"})
    r.raise_for_status()
    return r.json()["id_token"]


def verify_id_token(token: str, nonce: str) -> dict:
    global _certs
    if _certs is None:
        _certs = PyJWKClient(CERTS_URL, cache_keys=True, lifespan=3600)
    key = _certs.get_signing_key_from_jwt(token)
    claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=settings.google_client_id, issuer=ISSUERS)
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise ValueError("nonce mismatch")
    return claims


def _page(status: int, title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
        '<body style="font-family:Inter,system-ui,sans-serif;background:#f4faff;color:#0f1f45;display:grid;place-items:center;min-height:100vh;margin:0">'
        '<div style="background:#fff;border:1px solid #d9e8f5;border-radius:20px;padding:32px;max-width:420px;box-shadow:0 8px 28px rgba(11,42,111,.1)">'
        f'<h1 style="margin:0 0 8px;color:#0b2a6f;font-size:22px">{html.escape(title)}</h1><p style="color:#5a6b8c">{html.escape(body)}</p>'
        '<a href="/auth/login" style="display:inline-block;margin-top:8px;background:#0b2a6f;color:#fff;text-decoration:none;'
        'padding:10px 20px;border-radius:999px;font-weight:600">Sign in with Google</a></div></body>', status_code=status)


@router.get("/login")
def login():
    if not enabled():
        return _page(404, "Sign-in is not set up", "Google sign-in is not configured for this app.")
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    url = AUTH_URL + "?" + urlencode({
        "client_id": settings.google_client_id, "redirect_uri": f"{_base()}/auth/callback", "response_type": "code",
        "scope": "openid email", "state": state, "nonce": nonce, "prompt": "select_account"})
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(STATE, _sign({"s": state, "n": nonce}, STATE_TTL), max_age=STATE_TTL, httponly=True, samesite="lax", secure=_secure())
    return resp


@router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    st = _read(request.cookies.get(STATE))
    if not enabled() or error or not code or not st or not hmac.compare_digest(str(st.get("s", "")), state):
        return _page(400, "Sign-in did not complete", "Please try again.")
    try:
        idt = await run_in_threadpool(exchange_code, code)
        claims = await run_in_threadpool(verify_id_token, idt, str(st.get("n", "")))
    except Exception:  # bad code, bad signature, wrong audience, Google unreachable: all mean no session
        return _page(400, "Sign-in did not complete", "Please try again.")
    email = str(claims.get("email") or "").lower()
    if claims.get("email_verified") is not True or email not in allowed():
        return _page(403, "This Google account is not allowed", "Ask the owner to add your email, or sign in with a different account.")
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(SESSION, _sign({"email": email}, SESSION_TTL), max_age=SESSION_TTL, httponly=True, samesite="lax", secure=_secure())
    resp.delete_cookie(STATE)
    return resp


def missing() -> list[str]:
    """Names (never values) of the settings that keep sign-in switched off, so a misconfigured deploy can be diagnosed from outside."""
    out = []
    if not settings.google_client_id:
        out.append("GOOGLE_CLIENT_ID")
    if not settings.google_client_secret:
        out.append("GOOGLE_CLIENT_SECRET")
    if not allowed():
        out.append("ALLOWED_EMAILS")
    return out


@router.get("/me")
def me(request: Request):
    body = {"auth": enabled(), "email": session_email(request)}
    if not body["auth"]:
        body["missing"] = missing()
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@router.get("/logout")
def logout():
    resp = _page(200, "Signed out", "You have been signed out.")
    resp.delete_cookie(SESSION)
    return resp


async def gate(request: Request, call_next):
    """Replaces the Cloudflare-only gate: either method alone is enough, and with neither configured the site is open."""
    cf_on, g_on = access.enabled(), enabled()
    path = request.url.path
    if not (cf_on or g_on) or any(path == p or path.startswith(p) for p in OPEN_PATHS):
        return await call_next(request)
    if g_on and len(settings.session_secret) < 32:  # misconfigured: fail closed, never open
        return JSONResponse({"detail": "Sign-in is misconfigured: SESSION_SECRET must be at least 32 characters."}, status_code=503)
    if cf_on:
        token = request.headers.get("cf-access-jwt-assertion", "")
        if token and await run_in_threadpool(access.valid, token):
            return await call_next(request)
    if g_on and session_email(request):
        return await call_next(request)
    if g_on:
        if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
            return RedirectResponse("/auth/login", status_code=302)
        return JSONResponse({"detail": "Sign in required", "login": "/auth/login"}, status_code=401)
    where = settings.console_url or settings.public_base_url
    return JSONResponse({"detail": f"Sign in through {where} to use this app."}, status_code=403)
