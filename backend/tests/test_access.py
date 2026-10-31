import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import access
from app.core.config import settings
from app.main import app

TEAM, AUD = "team.cloudflareaccess.com", "aud-123"
client = TestClient(app)
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwks:
    def get_signing_key_from_jwt(self, token):
        class K:
            key = KEY.public_key()
        return K()


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setattr(settings, "access_team_domain", TEAM)
    monkeypatch.setattr(settings, "access_aud", AUD)
    monkeypatch.setattr(access, "_client", FakeJwks())


def token(**over):
    claims = {"aud": AUD, "iss": f"https://{TEAM}", "email": "me@example.com", "exp": 4102444800, **over}
    return jwt.encode(claims, KEY, algorithm="RS256")


def test_no_token_is_refused():
    r = client.get("/api/v1/merchants")
    assert r.status_code == 403 and "Sign in" in r.json()["detail"]
    assert client.get("/").status_code == 403


def test_valid_token_is_let_in():
    assert client.get("/api/v1/merchants", headers={"cf-access-jwt-assertion": token()}).status_code == 200


@pytest.mark.parametrize("bad", [dict(aud="other"), dict(iss="https://evil.example.com"), dict(exp=1)])
def test_wrong_audience_issuer_or_expired_token_is_refused(bad):
    assert client.get("/api/v1/merchants", headers={"cf-access-jwt-assertion": token(**bad)}).status_code == 403


def test_a_token_signed_by_someone_else_is_refused():
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode({"aud": AUD, "iss": f"https://{TEAM}", "exp": 4102444800}, other, algorithm="RS256")
    assert client.get("/api/v1/merchants", headers={"cf-access-jwt-assertion": forged}).status_code == 403


def test_health_checks_and_bolna_endpoints_stay_open():
    assert client.get("/readyz").status_code == 200
    assert client.get("/healthz").status_code == 200
    # reaches the app (its own secret check answers), not the Access gate
    assert client.post("/api/v1/voice/tools/get_settlement_status", json={}).status_code == 403
    assert "Sign in" not in client.post("/api/v1/voice/tools/get_settlement_status", json={}).text
    assert client.post("/api/v1/voice/events", json={"id": "x"}).status_code in (403, 422)


def test_gate_is_off_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "access_team_domain", "")
    assert client.get("/api/v1/merchants").status_code == 200
