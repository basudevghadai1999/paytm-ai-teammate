import os

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text

from app import seed, tickets
from app.agent import run_ticket
from app.core.config import settings
from app.core.db import db, engine
from app.llm import LLM, get_llm
from app.voice import router as voice_router

app = FastAPI(title="Paytm AI Teammate", docs_url="/api/docs" if settings.environment != "production" else None, redoc_url=None)
api = APIRouter(prefix="/api/v1")


class NewTicket(BaseModel):
    merchant_id: str
    message: str = Field(min_length=1, max_length=2000)
    email: str | None = Field(default=None, max_length=254)  # optional on the chat path; confirmations go here


class NewMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ResolveEscalation(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "revision": settings.git_revision}


@app.get("/readyz")
def readyz():
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
    except Exception:
        return JSONResponse({"ok": False}, status_code=503)
    return {"ok": True}


@api.get("/merchants")
def merchants() -> list[dict]:
    with db() as d:
        return d.all("select id, name, owner_name, category, city from tm_merchants order by name")


@api.post("/tickets", status_code=201)
def create_ticket(body: NewTicket, llm: LLM = Depends(get_llm)) -> dict:
    with db() as d:
        if not d.one("select 1 as x from tm_merchants where id = :m", m=body.merchant_id):
            raise HTTPException(404, "Unknown merchant")
        tid = tickets.create_ticket(d, body.merchant_id, body.message, body.email)
    run_ticket(tid, llm)
    with db() as d:
        return tickets.ticket_detail(d, tid)


@api.post("/tickets/{ticket_id}/messages")
def add_message(ticket_id: int, body: NewMessage, llm: LLM = Depends(get_llm)) -> dict:
    with db() as d:
        t = d.one("select status from tm_tickets where id = :t for update", t=ticket_id)
        if not t:
            raise HTTPException(404, "Unknown ticket")
        if t["status"] != "awaiting_merchant":
            raise HTTPException(409, "Ticket is not waiting for a reply")
        d.run("insert into tm_messages (ticket_id, role, content) values (:t, 'merchant', :c)", t=ticket_id, c=body.message)
        d.run("update tm_tickets set status = 'open' where id = :t", t=ticket_id)
    run_ticket(ticket_id, llm)
    with db() as d:
        return tickets.ticket_detail(d, ticket_id)


@api.get("/tickets")
def list_tickets() -> list[dict]:
    with db() as d:
        return tickets.list_tickets(d)


@api.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int) -> dict:
    with db() as d:
        t = tickets.ticket_detail(d, ticket_id)
    if not t:
        raise HTTPException(404, "Unknown ticket")
    return t


@api.post("/escalations/{escalation_id}/resolve")
def resolve_escalation(escalation_id: int, body: ResolveEscalation) -> dict:
    with db() as d:
        if not tickets.resolve_escalation(d, escalation_id, body.note):
            raise HTTPException(404, "No open escalation with that id")
    return {"ok": True}


@api.get("/metrics")
def metrics() -> dict:
    with db() as d:
        return tickets.metrics(d)


@api.post("/demo/reset")
def demo_reset() -> dict:
    if settings.environment == "production" and not settings.allow_demo_reset:
        raise HTTPException(403, "Demo reset is disabled")
    with db() as d:
        seed.reset(d)
    return {"ok": True}


app.include_router(api)
app.include_router(voice_router)

# Built frontend, copied into ./static by the Dockerfile. Absent in local dev (Vite serves it).
STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.isdir(STATIC):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = os.path.join(STATIC, path)
        return FileResponse(f if path and os.path.isfile(f) else os.path.join(STATIC, "index.html"))
