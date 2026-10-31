# Architecture

## Overview
Modular monolith, same shape as COOLops: **FastAPI + SQLAlchemy (raw SQL) + Alembic + PostgreSQL**, with a **React + TypeScript + Vite** frontend served as static files by the backend. One Docker image, one Render web service. The merchant talks to the teammate **by phone** through **Bolna**; confirmations go out by **email** through **Resend**.

```
Merchant's phone <--call--> Bolna voice agent (Sarvam voice, Deepgram Hindi transcriber, GPT-4.1-mini)
                                 |  custom-function tool calls  (POST /api/v1/voice/tools/{tool}, bearer secret)
                                 |  status webhook              (POST /api/v1/voice/events)
                                 v
Merchant call screen (React) --> FastAPI --> verify call with Bolna --> guarded tools (app/tools.py)
Ops console (React) ----------->    |                                         |
                                    |                                         +--> simulated systems (tm_* tables)
                                    |                                         +--> Resend (confirmation + emergency alert emails)
                                    +--> Postgres (Supabase, shared with COOLops)
Chat path (tests and evals): POST /api/v1/tickets --> agent loop --> NVIDIA Nemotron (tool calling) --> same guarded tools
```

On a call, **Bolna's model drives the conversation** and calls our tool endpoints; our code decides what is allowed. On the chat path (used by the eval harness and tests, no phone needed) our own agent loop drives the same tools. Both paths share one set of guardrails.

## Reused from COOLops
| Item | Reuse |
|---|---|
| Database | Same Supabase Postgres, same `DATABASE_URL` (runtime role `coolops_app`) and `MIGRATION_DATABASE_URL` (owner role) |
| Config pattern | `pydantic-settings` `Settings` class, `.env` locally, env vars on Render |
| DB access | Thin raw-SQL helpers with `hide_parameters=True`, so failed statements do not log merchant data |
| Dockerfile | Node build stage for the frontend, Python 3.13-slim runtime, `alembic upgrade head` then `uvicorn` |
| Render, CI | `render.yaml` free web service, `/readyz` health check, GitHub Actions (backend with Postgres, frontend) |
| Bolna pattern | Custom-function tools carrying `{call_sid}`, per-call identity check against Bolna's API, status webhook |
| Frontend toolchain | React 19, Vite, TypeScript, `recharts` |

Not reused: the COOLops Bolna **agent**. This app has its own agent; applying our setup rewrites an agent's prompt, tools and webhook.

## LLMs
| Where | Model |
|---|---|
| Chat path (agent loop, evals) | NVIDIA `nemotron-3.5-super-vl-120b-a12b` with thinking on; Groq `openai/gpt-oss-120b` as a fallback (`LLM_PROVIDER=auto` uses NVIDIA when its key is set). Both are OpenAI-style tool calling over HTTP |
| Voice agent | Configured inside Bolna (GPT-4.1-mini, Sarvam bulbul:v3 voice, Deepgram nova-3 Hindi transcriber). `python -m app.apply_agent` sets its prompt, tools, webhook, transcriber language and voice language |

## Database rules (shared DB)
1. Only **new tables**, all prefixed `tm_`. No `ALTER`, `DROP` or data change on COOLops tables.
2. Alembic uses its own version table, `alembic_version_teammate`, so it never collides with COOLops' `alembic_version`.
3. Migrations grant table privileges to `coolops_app` only for `tm_*` tables.
4. No RLS on `tm_*`. Merchant isolation is enforced in the tool layer: the merchant id comes from the ticket (and, on a call, from the call row this app created when it dialled), never from model output.
5. Downgrade drops only `tm_*` objects.

## Data model (new tables)
| Table | Purpose |
|---|---|
| `tm_merchants` | Demo merchants: category, city, KYC status, device id and status |
| `tm_transactions` | Simulated payments: amount, mode, status, `customer_debited` |
| `tm_settlements` | Simulated settlements: amount, expected date, status (`settled`, `pending`, `on_hold`), hold reason |
| `tm_tickets` | One per issue: `channel` (`chat`/`voice`), status (`open`, `awaiting_merchant`, `resolved`, `escalated`), category (incl. `out_of_scope`), resolution summary, `resolved_by` (`ai`/`human`), `contact_email` (never returned by the API) |
| `tm_messages` | Conversation and notifications: roles `merchant`, `agent`, `human`; kind `chat` or `notification`; `channel` `email` or `simulated`; Resend message id |
| `tm_actions` | Audit log of every tool call: step, tool, args, result, `allowed` |
| `tm_escalations` | Handoff package: reason, summary, attempted steps, recommended action, status, `alerted_at` (emergency email sent) |
| `tm_calls` | One per phone call: Bolna execution id, status, last four digits of the number only, transcript, duration |

Migrations: `0001` core schema, `0002` voice (ticket channel, `tm_calls`), `0003` email (contact email, message channel, alert marker).

## API (v1)
| Endpoint | Purpose |
|---|---|
| `POST /api/v1/calls` | Dial the merchant: body `merchant_id`, `phone` (E.164), `email`. Only allowlisted numbers outside development; 3 calls a minute at most |
| `POST /api/v1/voice/tools/{tool}` | Called by the Bolna agent mid-call. Bearer secret, call verified with Bolna, merchant bound from the call row, runs through the guarded tools |
| `POST /api/v1/voice/events` | Bolna status webhook. Status and transcript are re-read from Bolna; escalates a dropped call; screens the transcript for emergencies |
| `POST /api/v1/tickets`, `POST /api/v1/tickets/{id}/messages` | Chat path used by tests and the eval harness |
| `GET /api/v1/tickets`, `GET /api/v1/tickets/{id}` | Console: list and detail with actions, call and transcript |
| `POST /api/v1/escalations/{id}/resolve` | Human closes an escalation |
| `GET /api/v1/merchants` | Demo merchant picker |
| `GET /api/v1/metrics` | Auto-resolution rate, time to resolution, escalation reasons, blocked actions, unsafe actions, out-of-scope count |
| `POST /api/v1/demo/reset` | Reset seed data (disabled in production unless `ALLOW_DEMO_RESET`) |
| `GET /healthz`, `GET /readyz` | Liveness and readiness (readyz checks the DB) |

## Frontend
Two views: **Merchant call** (pick a demo merchant, enter phone and email, press *Call me*, watch the call status, each agent step, the confirmation and the transcript) and **Ops console** (metrics with a chart, ticket list with a call tag, per-ticket conversation, call transcript and agent trace, escalation queue). Styled with the Paytm hackathon palette.

## Email
Resend, over HTTPS (`app/mailer.py`). The sender is an address on a domain verified in Resend (`EMAIL_FROM`). Three kinds of mail: the agent's confirmation (`send_notification`), the acknowledgement the code sends itself when a ticket resolves or escalates, and the urgent alert to the human support inbox (`SUPPORT_ALERT_EMAIL`) on emergency escalations. Resend accepting a message is not proof of delivery, and the UI only says "emailed" when Resend accepted it.
