# Deployment (copied from COOLops)

## Pipeline
Same as COOLops: GitHub push, Render builds the Docker image, container start runs migrations then the server.

```
git push -> GitHub Actions CI (tests + build) -> Render autoDeploy -> docker build
  -> container start: alembic upgrade head && uvicorn app.main:app
```

## Dockerfile (multi-stage, same as COOLops)
1. **web stage:** `node:22-slim`, `npm ci`, `npm run build` for the frontend.
2. **runtime stage:** `python:3.13-slim`, install backend from `pyproject.toml`, copy `app/`, `alembic.ini`, `alembic/`, and the built frontend into `./static`.
3. `CMD`: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'`.

## render.yaml
A single free web service, `runtime: docker`, `healthCheckPath: /readyz`, `autoDeploy: true`. Service name: `paytm-teammate` (a **new** Render service; do not reuse the COOLops one).

## Environment variables
| Variable | Source |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Same Supabase session-pooler URL and `coolops_app` role as COOLops |
| `MIGRATION_DATABASE_URL` | Same Supabase owner-role URL as COOLops; used only by Alembic at start |
| `GROQ_API_KEY` | Same key as COOLops |
| `GROQ_MODEL` | Optional, default `openai/gpt-oss-120b` |
| `PUBLIC_BASE_URL` | `https://<service>.onrender.com` |
| `AUTO_REFUND_LIMIT_INR` | Optional, default 2000 |

Secrets are set in the Render dashboard (`sync: false`) and in a local, git-ignored `.env`. They must never be committed. COOLops keeps credentials in `CREDENTIALS.md`, which is git-ignored; do the same.

## CI (GitHub Actions)
Same two jobs as COOLops:
- **backend:** Postgres 16 service, create owner and app roles, `pip install -e 'backend[dev]'`, `alembic upgrade head`, `pytest -q`. The CI database is a throwaway, not Supabase.
- **frontend:** Node 22, `npm ci && npm test && npm run build`.

## Shared-database safeguards
- Migration `0001` creates only `tm_*` tables, and grants privileges only on those.
- Version table `alembic_version_teammate` keeps migration history separate.
- Rollback: `alembic downgrade base` drops only `tm_*` tables.
- Take a quick look at the Supabase table list before the first deploy to confirm no `tm_` name already exists.

## Pre-demo checklist
1. Deploy at least a few hours before the demo and confirm `/readyz` returns OK.
2. Warm the free instance a few minutes before presenting (cold start).
3. Seed data is loaded and the three demo scenarios run once.
4. A screen recording of a successful run exists as a fallback.
