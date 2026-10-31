from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.core.config import settings
from app.main import app

ME, OTHER = "ghadaibasudev1234@gmail.com", "stranger@gmail.com"
client = TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "cid.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "google_client_secret", "gsecret")
    monkeypatch.setattr(settings, "allowed_emails", f"{ME}, second@gmail.com")
    monkeypatch.setattr(settings, "session_secret", "x" * 40)
    monkeypatch.setattr(settings, "public_base_url", "https://paytm.example.com")
    monkeypatch.setattr(settings, "console_url", "")
    monkeypatch.setattr(auth, "exchange_code", lambda code: f"idtoken-{code}")


def google_says(monkeypatch, email, verified=True):
    monkeypatch.setattr(auth, "verify_id_token", lambda tok, nonce: {"email": email, "email_verified": verified})


def sign_in(monkeypatch, email):
    """Run the whole flow with a fresh client; returns the client holding the session cookie (or none)."""
    google_says(monkeypatch, email)
    c = TestClient(app, base_url="https://testserver", follow_redirects=False)
    r = c.get("/auth/login")
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    return c, c.get("/auth/callback", params={"code": "abc", "state": state})


def test_anonymous_visitors_are_sent_to_sign_in_or_refused():
    r = client.get("/", headers={"accept": "text/html"})
    assert r.status_code == 302 and r.headers["location"] == "/auth/login"
    r = client.get("/api/v1/merchants")
    assert r.status_code == 401 and r.json()["login"] == "/auth/login"
    assert client.get("/api/v1/tickets").status_code == 401


def test_login_redirects_to_google_with_the_right_parameters():
    r = client.get("/auth/login")
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert r.headers["location"].startswith("https://accounts.google.com/")
    assert q["client_id"] == ["cid.apps.googleusercontent.com"] and q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["https://paytm.example.com/auth/callback"] and "state" in q and "nonce" in q
    assert "pt_state" in r.headers["set-cookie"] and "HttpOnly" in r.headers["set-cookie"]


def test_an_allowed_account_gets_in(monkeypatch):
    c, r = sign_in(monkeypatch, ME.upper())  # case does not matter
    assert r.status_code == 302 and r.headers["location"] == "/"
    cookie = r.headers["set-cookie"]
    assert "pt_session=" in cookie and "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    assert c.get("/api/v1/merchants").status_code == 200
    assert c.get("/auth/me").json() == {"auth": True, "email": ME}


def test_any_other_google_account_is_refused(monkeypatch):
    c, r = sign_in(monkeypatch, OTHER)
    assert r.status_code == 403 and "not allowed" in r.text and "pt_session" not in r.headers.get("set-cookie", "")
    assert c.get("/api/v1/merchants").status_code == 401


def test_an_unverified_email_is_refused(monkeypatch):
    google_says(monkeypatch, ME, verified=False)
    c = TestClient(app, base_url="https://testserver", follow_redirects=False)
    state = parse_qs(urlparse(c.get("/auth/login").headers["location"]).query)["state"][0]
    assert c.get("/auth/callback", params={"code": "abc", "state": state}).status_code == 403


def test_a_wrong_state_or_missing_cookie_fails(monkeypatch):
    google_says(monkeypatch, ME)
    c = TestClient(app, base_url="https://testserver", follow_redirects=False)
    c.get("/auth/login")
    assert c.get("/auth/callback", params={"code": "abc", "state": "forged"}).status_code == 400
    assert TestClient(app, base_url="https://testserver", follow_redirects=False).get("/auth/callback", params={"code": "abc", "state": "x"}).status_code == 400
    assert c.get("/auth/callback", params={"error": "access_denied", "state": "x"}).status_code == 400


def test_a_forged_session_cookie_is_ignored():
    c = TestClient(app, base_url="https://testserver", follow_redirects=False)
    c.cookies.set("pt_session", "not-a-real-token")
    assert c.get("/api/v1/merchants").status_code == 401
    import jwt
    forged = jwt.encode({"email": ME, "exp": 4102444800}, "some-other-secret-key-with-32-chars!!", algorithm="HS256")
    c.cookies.set("pt_session", forged)
    assert c.get("/api/v1/merchants").status_code == 401


def test_removing_an_email_locks_that_person_out_at_once(monkeypatch):
    c, _ = sign_in(monkeypatch, ME)
    assert c.get("/api/v1/merchants").status_code == 200
    monkeypatch.setattr(settings, "allowed_emails", "second@gmail.com")
    assert c.get("/api/v1/merchants").status_code == 401


def test_health_checks_sign_in_pages_and_bolna_endpoints_stay_open():
    assert client.get("/readyz").status_code == 200 and client.get("/healthz").status_code == 200
    assert client.get("/auth/me").json() == {"auth": True, "email": None}
    assert client.post("/api/v1/voice/tools/get_settlement_status", json={}).status_code == 403  # its own secret check, not the sign-in gate
    assert "Sign in" not in client.post("/api/v1/voice/tools/get_settlement_status", json={}).text


def test_logout_clears_the_session(monkeypatch):
    c, _ = sign_in(monkeypatch, ME)
    r = c.get("/auth/logout")
    assert r.status_code == 200 and "pt_session" in r.headers["set-cookie"]


def test_a_weak_session_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "short")
    assert client.get("/api/v1/merchants").status_code == 503


def test_without_google_settings_the_site_is_open(monkeypatch):
    monkeypatch.setattr(settings, "allowed_emails", "")
    assert client.get("/api/v1/merchants").status_code == 200


def test_google_and_cloudflare_access_can_be_used_together(monkeypatch):
    from app import access
    monkeypatch.setattr(settings, "access_team_domain", "team.cloudflareaccess.com")
    monkeypatch.setattr(settings, "access_aud", "aud")
    monkeypatch.setattr(access, "valid", lambda t: t == "good")
    assert client.get("/api/v1/merchants", headers={"cf-access-jwt-assertion": "good"}).status_code == 200
    assert client.get("/api/v1/merchants", headers={"cf-access-jwt-assertion": "bad"}).status_code == 401
