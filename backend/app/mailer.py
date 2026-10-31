"""Email through Resend. 200 with an id means Resend accepted it; delivery itself is not confirmed here."""
import html

import httpx

from app.core.config import settings

API = "https://api.resend.com/emails"


class MailError(Exception):
    pass


def configured() -> bool:
    return bool(settings.resend_api_key and settings.email_from)


def _html(subject: str, text: str) -> str:
    body = "<br>".join(html.escape(line) for line in text.split("\n"))
    return ('<div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;border:1px solid #d9e8f5;border-radius:14px;overflow:hidden">'
            f'<div style="background:#0b2a6f;color:#fff;padding:16px 20px;font-weight:700">Paytm <span style="color:#4fb7f6">AI Teammate</span></div>'
            f'<div style="padding:20px;color:#0f1f45;line-height:1.55"><h3 style="margin:0 0 10px;color:#0b2a6f">{html.escape(subject)}</h3>{body}</div>'
            '<div style="padding:12px 20px;background:#f4faff;color:#5a6b8c;font-size:12px">Demo message. Payments, settlements and devices in this demo are simulated.</div></div>')


def send(to: str, subject: str, text: str) -> str:
    """Returns Resend's message id, or raises MailError. Never logs the address or the body."""
    if not configured():
        raise MailError("email is not configured")
    try:
        r = httpx.post(API, headers={"Authorization": f"Bearer {settings.resend_api_key}"}, timeout=10,
                       json={"from": settings.email_from, "to": [to], "subject": subject, "text": text, "html": _html(subject, text)})
    except httpx.HTTPError as e:
        raise MailError(type(e).__name__)
    if r.status_code not in (200, 201, 202):
        raise MailError(f"resend http {r.status_code}: {r.text[:160]}")
    mid = r.json().get("id")
    if not mid:
        raise MailError("resend response had no id")
    return mid
