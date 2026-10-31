# Paytm AI Teammate

Hackathon project, **Track 3: Autonomous AI Teammates**. An AI teammate that handles Paytm merchant support tickets end to end. It resolves issues, takes actions across systems, and escalates to a human only when needed.

## Docs

| File | Purpose |
|---|---|
| [docs/BRD.md](docs/BRD.md) | Business problem, objectives, business rules, risks, path to production |
| [docs/FRD.md](docs/FRD.md) | Functional requirements, workflows, non-functional requirements, traceability |
| [docs/PRD.md](docs/PRD.md) | Problem, users, scope, success metrics |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data model, what is reused from COOLops |
| [docs/AGENT_DESIGN.md](docs/AGENT_DESIGN.md) | Agent loop, tools, decision policy, guardrails, escalation |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Render + Supabase pipeline copied from COOLops, env vars, CI |
| [docs/DEMO_AND_EVALS.md](docs/DEMO_AND_EVALS.md) | Scenarios, eval harness, demo script, build timeline |

## Reuse from COOLops (decided)

- **LLM:** Groq, model `openai/gpt-oss-120b`, same `GROQ_API_KEY`.
- **Database:** the same Supabase Postgres. This app only adds new `tm_*` tables and never touches COOLops tables.
- **Deployment:** the same pipeline: multi-stage Dockerfile, Render free web service, `alembic upgrade head` at start, GitHub Actions CI.

## Status

Built from the docs, **not yet run**: this machine had no Node, no Python 3.12+ and no Postgres, so nothing has been executed or tested. First run in CI or Docker.

| Part | Where |
|---|---|
| Schema (`tm_*` only, own version table) | `backend/alembic/versions/0001_teammate_schema.py` |
| Guarded tools | `backend/app/tools.py` |
| Agent loop + fraud/legal pre-screen | `backend/app/agent.py` |
| API, metrics | `backend/app/main.py`, `backend/app/tickets.py` |
| Seed (one merchant per scenario) | `backend/app/seed.py` |
| Tests (scripted LLM, needs Postgres) | `backend/tests/` |
| Eval harness (real Groq) | `python -m evals.run_evals` from `backend/` |
| Merchant chat + ops console | `frontend/src/` |
| Docker, Render, CI | `Dockerfile`, `render.yaml`, `.github/workflows/ci.yml` |

Voice: merchants talk to the teammate by phone through Bolna (`backend/app/voice.py`, `backend/app/bolna.py`). The Bolna agent calls the same guarded tools mid-call. Setup: create a new Bolna agent, set `BOLNA_PAYTM_AGENT_ID`, `BOLNA_WEBHOOK_SECRET`, `DEMO_CALL_ALLOWLIST`, then run `python -m app.apply_agent` from `backend/`.

Not built: FR-504 (human approves a recommended refund from the console; over-limit refunds are blocked by design, so this needs a decision), 
