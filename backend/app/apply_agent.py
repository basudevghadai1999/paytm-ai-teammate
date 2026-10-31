"""Write the voice prompt, tools and webhook into the Paytm Bolna agent. Run deliberately:
    python -m app.apply_agent
Needs BOLNA_API_KEY, BOLNA_PAYTM_AGENT_ID, BOLNA_WEBHOOK_SECRET and PUBLIC_BASE_URL (https, reachable by Bolna)."""
from app import bolna
from app.core.config import settings

for name in ("bolna_api_key", "bolna_paytm_agent_id", "bolna_webhook_secret"):
    if not getattr(settings, name):
        raise SystemExit(f"{name.upper()} is not set")
if not settings.public_base_url.startswith("https://"):
    raise SystemExit("PUBLIC_BASE_URL must be an https URL that Bolna can reach (a tunnel or the Render URL)")
bolna.apply_agent(settings.public_base_url)
agent = bolna._get(f"/v2/agent/{settings.bolna_paytm_agent_id}")
names = [t.get("name") for task in agent.get("tasks", []) for t in ((task.get("tools_config") or {}).get("api_tools") or {}).get("tools", []) or []]
print("live transfer for emergencies:", "ON" if bolna.transfer_number() else "off (SUPPORT_TRANSFER_NUMBER not set; emergencies stay a callback)")
print("applied; agent now has tools:", names, "| webhook:", agent.get("webhook_url"))
