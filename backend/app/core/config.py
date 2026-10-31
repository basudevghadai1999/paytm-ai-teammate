import os

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

    auto_refund_limit_inr: int = 2000
    agent_step_limit: int = 8
    allow_demo_reset: bool = False  # POST /demo/reset; always on outside production


settings = Settings()
if settings.git_revision == "unknown":
    settings.git_revision = os.environ.get("RENDER_GIT_COMMIT", "unknown")
