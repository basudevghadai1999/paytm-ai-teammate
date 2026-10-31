# Architecture

## Overview
Modular monolith, same shape as COOLops: **FastAPI + SQLAlchemy (raw SQL) + Alembic + PostgreSQL**, with a **React + TypeScript + Vite** frontend served as static files by the backend. One Docker image, one Render web service.

```
Merchant chat (React) ──┐
                        ├──> FastAPI ──> Agent loop ──> Groq (gpt-oss-120b, tool calling)
Ops console (React) ────┘        │            │
                                 │            └──> Tools (guardrails in code) ──> simulated systems (tm_* tables)
                                 └──> Postgres (Supabase, shared with COOLops)
```

## Reused from COOLops
| Item | Reuse |
|---|---|
| LLM | Groq, `openai/gpt-oss-120b`, `GROQ_API_KEY`. COOLops only uses JSON mode; this app adds OpenAI-style tool calling on the same endpoint |
| Database | Same Supabase Postgres, same `DATABASE_URL` (runtime role `coolops_app`) and `MIGRATION_DATABASE_URL` (owner role) |
| Config pattern | `pydantic-settings` `Settings` class, `.env` locally, env vars on Render |
| DB access | Thin raw-SQL helpers with `hide_parameters=True`, so failed statements do not log merchant data |
| Dockerfile | Node build stage for the frontend, Python 3.13-slim runtime, `alembic upgrade head` then `uvicorn` |
| Render | `render.yaml` free web service, `/readyz` health check, `autoDeploy` |
| CI | GitHub Actions: backend (Postgres service, migrate, pytest) and frontend (test, build) |
| Frontend toolchain | React 19, Vite, TypeScript, same tsconfig files |

## Database rules (shared DB)
1. Only **new tables**, all prefixed `tm_`. No `ALTER`, `DROP` or data change on COOLops tables.
2. Alembic uses its own version table, `alembic_version_teammate`, so it never collides with COOLops' `alembic_version`.
3. Migrations grant table and sequence privileges to `coolops_app` only for `tm_*` objects.
4. No RLS on `tm_*`. COOLops' tenant RLS does not apply because these tables are not tenant-scoped. Merchant isolation is enforced in the tool layer: the merchant id comes from the ticket, never from model output.
5. Downgrade drops only `tm_*` tables.

## Data model (new tables)
| Table | Purpose |
|---|---|
| `tm_merchants` | Demo merchants: category, city, KYC status, device id and status |
| `tm_transactions` | Simulated payments: amount, mode, status, `customer_debited` |
| `tm_settlements` | Simulated settlements: amount, expected date, status (`settled`, `pending`, `on_hold`), hold reason |
| `tm_tickets` | One per issue: status (`open`, `awaiting_merchant`, `resolved`, `escalated`), category, resolution summary, `resolved_by` (`ai`/`human`) |
| `tm_messages` | Conversation: roles `merchant`, `agent`, `human` |
| `tm_actions` | Audit log of every tool call: step, tool, args, result, `allowed` |
| `tm_escalations` | Handoff package: reason, summary, attempted steps, recommended action, status |

## API (v1)
| Endpoint | Purpose |
|---|---|
| `POST /api/v1/tickets` | Merchant raises a ticket, agent runs, response includes the reply and steps |
| `POST /api/v1/tickets/{id}/messages` | Merchant follow-up, agent resumes |
| `GET /api/v1/tickets`, `GET /api/v1/tickets/{id}` | Console: list and detail with actions |
| `POST /api/v1/escalations/{id}/resolve` | Human closes an escalation |
| `GET /api/v1/merchants` | Demo merchant picker |
| `GET /api/v1/metrics` | Auto-resolution rate, time to resolution, escalation reasons |
| `GET /healthz`, `GET /readyz` | Liveness and readiness (readyz checks the DB) |

## Frontend
Two views: **Merchant chat** and **Ops console** (ticket list, live step trace, escalation queue, metrics). Charts use `recharts` as in COOLops.

## Note on files already created
Before the "docs only" instruction, a partial backend scaffold was written in `backend/` (config, db helpers, Groq tool-calling client, Alembic env and migration `0001`) and tsconfig/vite files in `frontend/`. They follow the design above. They are unreviewed and untested, and can be deleted or kept when you decide.
