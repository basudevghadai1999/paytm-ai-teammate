# Deployment (copied from COOLops, plus voice and email)

## Pipeline
Same as COOLops: GitHub push, Render builds the Docker image, container start runs migrations then the server.

```
git push -> GitHub Actions CI (tests + build) -> Render autoDeploy -> docker build
  -> container start: alembic upgrade head && python -m app.seed_if_empty && uvicorn app.main:app
```

## Dockerfile (multi-stage, same as COOLops)
1. **web stage:** `node:22-slim`, `npm ci`, `npm run build` for the frontend.
2. **runtime stage:** `python:3.13-slim`, install backend from `pyproject.toml`, copy `app/`, `alembic.ini`, `alembic/`, and the built frontend into `./static`.
3. `CMD`: `alembic upgrade head && python -m app.seed_if_empty && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'`. The seed loads only when `tm_merchants` is empty, so redeploys keep existing tickets.

## render.yaml
A single free web service `paytm-teammate`, `runtime: docker`, `healthCheckPath: /readyz`, `autoDeploy: true`. A **new** Render service; do not reuse the COOLops one. The repository can be private: Render connects through its GitHub app.

## Environment variables
| Variable | Source |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL`, `MIGRATION_DATABASE_URL` | Same Supabase session-pooler URLs and roles as COOLops (runtime `coolops_app`, owner for Alembic only) |
| `NVIDIA_API_KEY`, `NVIDIA_MODEL` | Chat-path model (default `nvidia/nemotron-3.5-super-vl-120b-a12b`); used when set |
| `GROQ_API_KEY`, `GROQ_MODEL` | Fallback model (`openai/gpt-oss-120b`); `LLM_PROVIDER=auto` picks NVIDIA first |
| `BOLNA_API_KEY` | Bolna account key |
| `BOLNA_PAYTM_AGENT_ID` | This app's own Bolna agent. **Never** the COOLops agent |
| `BOLNA_WEBHOOK_SECRET` | A long random string, identical in Render and in the Bolna agent's tool definitions (written by `apply_agent`) |
| `DEMO_CALL_ALLOWLIST` | Comma-separated E.164 numbers the demo may dial. Empty in production means calls are off |
| `RESEND_API_KEY` | Resend key |
| `EMAIL_FROM` | An address on a domain verified in Resend. The default sandbox sender only delivers to the Resend account owner |
| `SUPPORT_ALERT_EMAIL` | Human support inbox for emergency escalations; empty means no alert email |
| `PUBLIC_BASE_URL` | `https://<service>.onrender.com`; written into the Bolna agent's tool and webhook URLs |
| `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD` | Cloudflare Access gate; both set turns it on (see Access control) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ALLOWED_EMAILS`, `SESSION_SECRET` | Google sign-in (see Access control). All of the first three set turns it on |
| `CONSOLE_URL` | The address people use (the Cloudflare hostname); used for links in emails. Falls back to `PUBLIC_BASE_URL` |
| `AUTO_REFUND_LIMIT_INR` | Optional, default 2000 |
| `ALLOW_DEMO_RESET` | `false` by default; `true` lets the console's reset button delete all tickets |

Secrets are set in the Render dashboard (`sync: false`) and in a local, git-ignored `.env`. They must never be committed.

## Access control (private during development)
Two independent gates; either one, or both, can be turned on. With neither set the site is open.

### Google sign-in (built into the app)
Only the Google accounts listed in `ALLOWED_EMAILS` can use the site (`app/auth.py`). Visitors are sent to Google, and after sign-in the app checks the verified email against the list; anyone else is refused, even if Google let them through. A signed, HttpOnly session cookie lasts 8 hours, and the list is re-checked on every request, so removing an email takes effect immediately. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ALLOWED_EMAILS` and `SESSION_SECRET` (32+ characters; a weak one makes the site return 503 rather than open). In Google Cloud, add `<site>/auth/callback` as an authorized redirect URI of the OAuth client (and `http://localhost:8000/auth/callback` for local use). Anonymous visitors see a public sign-in page at `/auth/login` (what the app does, what is real and what is simulated, and a *Sign in with Google* button that starts the flow at `/auth/google`); signed-in visitors skip it. Open paths: `/healthz`, `/readyz`, `/auth/*` and `/api/v1/voice/*` (Bolna's own endpoints, protected by their bearer secret and call verification).

### Cloudflare Access (optional, in front of the site)
The site is private: Cloudflare Access asks for an email, sends a one-time code, and only listed emails get in.
- **Gate in the app** (`app/access.py`, enforced by `app/auth.py`): when `ACCESS_TEAM_DOMAIN` and `ACCESS_AUD` are set, every request must carry a valid Cloudflare Access token (signature, audience and issuer checked), so the plain `onrender.com` address cannot be used to get around Access. Open paths: `/healthz`, `/readyz` (Render's health checks) and `/api/v1/voice/*` (Bolna cannot type a code; these endpoints have their own bearer secret and verify every call with Bolna). Unset, the gate is off.
- **Setup:** add a custom domain in Render (for example `paytm.basudevtech.com`); in Cloudflare DNS add a proxied CNAME to the Render address; in Zero Trust turn on One-time PIN, create a self-hosted Access application for that hostname with an Allow policy for the permitted emails, and a second application for path `/api/v1/voice` with a Bypass policy; then set `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD` and `CONSOLE_URL` in Render. The Bolna agent can keep calling the `onrender.com` address, because the voice paths are open.

## Bolna agent
1. Create a **new** agent in Bolna and choose its voice and transcriber (this deployment uses a Sarvam voice, Deepgram nova-3).
2. With the variables above set, run `python -m app.apply_agent` from `backend/`. It writes the voice prompt, the nine tools, the webhook, the Hindi transcriber language and the Hindi voice language into the agent, then you read the agent back to confirm. Re-run it whenever `PUBLIC_BASE_URL` or the prompt changes. A saved backup of an agent's previous config is the way back.
3. Place one controlled test call before any demo.

## CI (GitHub Actions)
`.github/workflows/ci.yml`, on every push and pull request:
- **backend:** Postgres 16 service, create owner and app roles, `pip install -e 'backend[dev]'`, `alembic upgrade head`, `pytest -q` (70 tests with a scripted model and a mocked Bolna and Resend; no API keys needed). The CI database is a throwaway, not Supabase.
- **frontend:** Node 22, `npm ci && npm test && npm run build`.

## Shared-database safeguards
- Migrations `0001` to `0003` create and alter only `tm_*` tables, and grant privileges only on those.
- Version table `alembic_version_teammate` keeps migration history separate.
- Rollback: `alembic downgrade base` drops only `tm_*` objects.
- Look at the Supabase table list before the first deploy to confirm no `tm_` name already exists.

## Pre-demo checklist
1. Deploy at least a few hours before the demo and confirm `/readyz` returns OK and `/healthz` shows the new revision.
2. **Warm the free instance** a few minutes before presenting: a cold start of up to a minute would make the first tool calls on a call time out.
3. Confirm the Bolna agent was applied against the live URL, and place a test call to the allowlisted number.
4. Confirm a confirmation email arrives, and that the emergency alert reaches `SUPPORT_ALERT_EMAIL`.
5. Seed data is loaded and the demo scenarios run once.
6. A screen recording of a successful call exists as a fallback.
