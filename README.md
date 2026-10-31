# Paytm AI Teammate

Hackathon project, **Track 3: Autonomous AI Teammates**. An AI teammate that takes **phone calls** from Paytm merchants, resolves their support issues end to end, takes actions across systems, and escalates to a human only when needed.

A merchant picks a demo profile, enters their number, and the teammate calls them. On the call it looks up settlements, payments and devices, refunds within policy, raises soundbox replacements, sends a simulated SMS, and closes the ticket. Anything risky (large refunds, KYC holds, fraud or legal threats) goes to a person with a full case summary.

Payments, settlements and devices are **simulated** (`tm_*` tables). The phone call and the **confirmation emails** (Resend) are real. SMS is not sent: Resend is email-only, so the app emails instead.

## How it works

```
Merchant's phone <--call--> Bolna voice agent (speech in/out, conversation)
                                 |  custom-function tool calls, verified per call
                                 v
                    FastAPI  /api/v1/voice/tools/*  ──>  guarded tools (app/tools.py)
                                 |                              |
Ops console (React) ──> /api/v1/tickets, /metrics        simulated systems (tm_* tables)
                                 v
                           Postgres (Supabase)
```

- **The model only proposes; code decides.** Every tool call goes through guardrails in `app/tools.py`: refund limit, one refund per transaction, refunds only for eligible payments, replacement only for a faulty device, and the merchant is bound from the call we placed, never from what the caller says.
- **Calls are verified.** Each tool call is checked with Bolna: the call must be a live execution of our agent that this app placed.
- **Never ends silently.** A call that drops before resolution escalates as `call_dropped`; an LLM outage escalates; a step limit escalates.
- **Confirmation by email.** The merchant types an email address in the call form (a spoken address is easily misheard). When the ticket resolves or escalates, the code itself sends an acknowledgement, and the agent's own `send_notification` is a real email too. The reply may only claim an email was sent if one really was.
- **Emergencies reach a human.** Fraud, a hacked account, legal threats and abusive or distressed merchants escalate straight away, and the support inbox (`SUPPORT_ALERT_EMAIL`) gets an urgent email with the case summary. As a safety net, after every call the merchant's side of the transcript (English and Hindi) is screened; if the agent missed an emergency, the ticket is reopened and escalated.
- **Everything is audited** in `tm_actions` (allowed or blocked) and shown in the ops console, together with the call transcript.

## Screens

- **Merchant call:** pick a demo merchant, enter your number, press *Call me*. Shows the call state, each step the agent takes, the SMS sent, and the transcript.
- **Ops console:** metrics (auto-resolution rate, time to resolution, blocked actions, unsafe actions), ticket list with a call tag, per-ticket conversation and agent steps, and the escalation queue where a human resolves a case.

The text-chat UI was replaced by the call screen. The chat API (`POST /api/v1/tickets`) and agent loop remain, because the eval harness and tests drive the same guarded tools without a phone.

## Stack

FastAPI, SQLAlchemy raw SQL, Alembic, PostgreSQL (Supabase), React 19 + TypeScript + Vite, Bolna (voice), NVIDIA `nemotron-3.5-super-vl-120b-a12b` for the chat agent (Groq `openai/gpt-oss-120b` as fallback), Docker, Render, GitHub Actions. Reused from COOLops: the database, deployment pipeline and Bolna integration pattern. This app only adds `tm_*` tables and never touches COOLops tables.

## Run locally

Needs Python 3.13, Node 22 and a Postgres with two roles (`coolops_owner`, `coolops_app`).

```bash
cp .env.example backend/.env        # fill in the keys
cd backend
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head      # creates tm_* tables
.venv/bin/python -m app.seed        # demo merchants and data
.venv/bin/pytest -q                 # 29 tests; scripted LLM, mocked Bolna, needs Postgres
.venv/bin/uvicorn app.main:app --port 8000

cd ../frontend && npm ci && npm run dev      # http://localhost:5173, proxies /api to :8000
```

`pytest` resets the seed data; rerun `python -m app.seed` afterwards.

## Voice setup (Bolna)

1. Create a **new** Bolna agent. Do not reuse the COOLops agent: applying this app's setup replaces the agent's prompt, tools and webhook. Choose the voice and transcriber in Bolna (Sarvam voice works; use a multilingual or Hindi transcriber for Hindi merchants).
2. Set in `backend/.env` (and in Render): `RESEND_API_KEY`, `EMAIL_FROM` (an address on a domain verified in Resend; the default sandbox sender only delivers to your own Resend account), `SUPPORT_ALERT_EMAIL`, `BOLNA_API_KEY`, `BOLNA_PAYTM_AGENT_ID`, `BOLNA_WEBHOOK_SECRET` (any long random string), `DEMO_CALL_ALLOWLIST` (comma-separated E.164 numbers the demo may dial), and `PUBLIC_BASE_URL` (an https address Bolna can reach, such as the Render URL).
3. From `backend/`, run `python -m app.apply_agent`. It writes the voice prompt, the tools and the webhook into the agent and reads the agent back to confirm. Run it again whenever `PUBLIC_BASE_URL` or the prompt changes.
4. Open the app, pick a merchant, enter an allowlisted number, press *Call me*.

Calling is restricted on purpose: the endpoint is public, so in production only numbers in `DEMO_CALL_ALLOWLIST` can be dialled (empty list means calls are off), and at most 3 calls start per minute.

## Deploy (Render)

`render.yaml` defines one free web service, `paytm-teammate`, built from the `Dockerfile` (Node build stage, Python 3.13 runtime). On start it runs `alembic upgrade head`, seeds demo data only if the merchants table is empty, then serves the API and the built frontend. Health check: `/readyz`.

Set the secrets listed in `render.yaml` in the Render dashboard: `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `NVIDIA_API_KEY`, `GROQ_API_KEY`, `RESEND_API_KEY`, `EMAIL_FROM`, `SUPPORT_ALERT_EMAIL`, `BOLNA_API_KEY`, `BOLNA_PAYTM_AGENT_ID`, `BOLNA_WEBHOOK_SECRET`, `DEMO_CALL_ALLOWLIST`, `PUBLIC_BASE_URL`. The free instance sleeps when idle and takes up to a minute to wake: open the app before placing a call.

Because the database is shared with COOLops, migrations create only `tm_*` tables, use their own version table (`alembic_version_teammate`), and `alembic downgrade base` drops only `tm_*` tables.

## CI

`.github/workflows/ci.yml` runs on every push and pull request: the backend job starts Postgres 16, applies the migrations and runs `pytest`; the frontend job runs `npm test` and `npm run build`. No API keys are needed.

## Evals

`python -m evals.run_evals` (from `backend/`) resets the seed data and runs the 10 scenarios from `docs/DEMO_AND_EVALS.md` against the real model, then prints correct-decision rate, auto-resolution rate, blocked and unsafe actions, and average resolution time. Last run: 10 of 10 decisions correct, 0 unsafe actions, about 4 seconds per AI-resolved ticket.

The auto-resolution rate over the whole set is about 40%, because half the scenarios are meant to escalate or be blocked; the PRD's 70% target only makes sense over the resolvable scenarios.

## Where things are

| Part | Where |
|---|---|
| Schema (`tm_*` only) | `backend/alembic/versions/0001_teammate_schema.py`, `0002_voice_calls.py` |
| Guarded tools | `backend/app/tools.py` |
| Agent loop, fraud and legal pre-screen (chat path) | `backend/app/agent.py` |
| Voice: call API, tool endpoints, status webhook | `backend/app/voice.py` |
| Bolna client, voice prompt, agent apply | `backend/app/bolna.py`, `backend/app/apply_agent.py` |
| LLM providers | `backend/app/llm.py` |
| API, metrics | `backend/app/main.py`, `backend/app/tickets.py` |
| Seed (one merchant per scenario) | `backend/app/seed.py` |
| Tests, evals | `backend/tests/`, `backend/evals/` |
| Frontend | `frontend/src/` (`Call.tsx`, `Console.tsx`) |

## Known limits

- On a live call, fraud and legal wording reaches the agent mid-call, so voice relies on its prompt and the escalation tool first, then the post-call transcript screen as a safety net. The screen is keyword-based, so unusual phrasing can slip past it.
- Resend accepting an email does not prove it was delivered or read.
- FR-504 (a human approves a recommended refund from the console) is not built: over-limit refunds are blocked by design, so approving one needs a policy decision.
- Bolna's custom-function JSON follows the COOLops integration; confirm it with a real test call after `apply_agent`.

## Docs

The documents below were written before the move from chat to phone calls. Where they say "chat", read "call"; the rest (policy, guardrails, data model, evals) still holds.

| File | Purpose |
|---|---|
| [docs/BRD.md](docs/BRD.md) | Business problem, objectives, business rules, risks, path to production |
| [docs/FRD.md](docs/FRD.md) | Functional requirements, workflows, non-functional requirements, traceability |
| [docs/PRD.md](docs/PRD.md) | Problem, users, scope, success metrics |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data model, what is reused from COOLops |
| [docs/AGENT_DESIGN.md](docs/AGENT_DESIGN.md) | Agent loop, tools, decision policy, guardrails, escalation |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Render + Supabase pipeline copied from COOLops, env vars, CI |
| [docs/DEMO_AND_EVALS.md](docs/DEMO_AND_EVALS.md) | Scenarios, eval harness, demo script, build timeline |
