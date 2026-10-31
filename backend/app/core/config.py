import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://coolops_app:coolops_app@localhost:5432/coolops"
    migration_database_url: str = ""
    environment: str = "development"
    git_revision: str = "unknown"
    public_base_url: str = "http://localhost:8000"

    llm_provider: str = "auto"  # auto = nvidia if NVIDIA_API_KEY is set, else groq
    nvidia_api_key: str = ""
    nvidia_model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    nvidia_enable_thinking: bool = True  # off: faster, but ignores the "ask when ambiguous" rule (eval scenario 7 passed 1 of 5)

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_reasoning_effort: str = "low"  # gpt-oss only; empty string omits the parameter

    bolna_api_key: str = ""
    bolna_base_url: str = "https://api.bolna.ai"
    bolna_paytm_agent_id: str = ""  # a NEW agent for this app; never the COOLops agent (BOLNA_AGENT_ID)
    bolna_webhook_secret: str = ""  # bearer secret Bolna sends to our tool endpoints
    demo_call_allowlist: str = ""   # comma-separated E.164 numbers the demo may dial; empty = disabled in production

    resend_api_key: str = Field("", validation_alias=AliasChoices("RESEND_API_KEY", "RESEND_API"))
    # Resend's sandbox sender only delivers to the Resend account owner; set EMAIL_FROM to an address on a verified domain to email merchants
    email_from: str = "Paytm AI Teammate <onboarding@resend.dev>"
    support_transfer_number: str = ""  # E.164 human support line; emergencies on a live call are transferred here. Empty = callback only
    support_alert_email: str = ""  # human support inbox for emergency escalations; empty = no alert email

    # Google sign-in. Client id + secret + ALLOWED_EMAILS all set = only those Google accounts can use the site.
    google_client_id: str = ""
    google_client_secret: str = Field("", validation_alias=AliasChoices("GOOGLE_CLIENT_SECRET", "GOOGLE_SECRET_ID"))
    allowed_emails: str = ""  # comma-separated Google account emails
    session_secret: str = ""  # signs the login cookie; 32+ characters

    # Cloudflare Access in front of the site. Both set = every request outside OPEN_PATHS must carry a valid Access token.
    access_team_domain: str = ""  # e.g. yourteam.cloudflareaccess.com
    access_aud: str = ""          # the Access application's Audience (AUD) tag
    console_url: str = ""         # human-facing address used in emails; falls back to PUBLIC_BASE_URL

    auto_refund_limit_inr: int = 2000
    agent_step_limit: int = 8
    allow_demo_reset: bool = False  # POST /demo/reset; always on outside production


settings = Settings()
if settings.git_revision == "unknown":
    settings.git_revision = os.environ.get("RENDER_GIT_COMMIT", "unknown")
