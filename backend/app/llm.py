import time

import httpx

from app.core.config import settings


MAX_RATE_LIMIT_RETRIES = 5
MAX_RATE_LIMIT_WAIT = 60.0


class LLMError(Exception):
    pass


class LLM:
    def chat(self, messages: list[dict], tools: list[dict]) -> dict:  # pragma: no cover - interface
        """Returns the assistant message dict: {"content": str|None, "tool_calls": [...]|None}."""
        raise NotImplementedError


class OpenAICompatLLM(LLM):
    """OpenAI-style tool calling over plain HTTP. Subclasses set the endpoint, key, model and extra body fields."""

    url = ""
    name = ""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def extra_body(self) -> dict:
        return {}

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        if not self.api_key:
            raise LLMError(f"{self.name} API key not configured")
        body = {"model": self.model, "temperature": 0, "messages": messages, "tools": tools, "tool_choice": "auto",
                **self.extra_body()}
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                r = httpx.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=60, json=body)
            except httpx.HTTPError as e:
                if attempt >= 1:
                    raise LLMError(type(e).__name__)
                continue  # one retry for a timeout or dropped connection
            if r.status_code >= 500 and attempt < 1:
                continue  # one retry for a transient server error
            if r.status_code != 429 or attempt == MAX_RATE_LIMIT_RETRIES:
                break
            try:  # tokens-per-minute limit: wait it out instead of failing the ticket
                wait = float(r.headers.get("retry-after", "10"))
            except ValueError:
                wait = 10.0
            time.sleep(min(wait, MAX_RATE_LIMIT_WAIT) + 0.5)
        if r.status_code != 200:
            raise LLMError(f"{self.name} http {r.status_code}: {r.text[:200]}")
        try:
            return r.json()["choices"][0]["message"]
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError(f"bad model output: {e}")


class GroqLLM(OpenAICompatLLM):
    url = "https://api.groq.com/openai/v1/chat/completions"
    name = "groq"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        super().__init__(api_key or settings.groq_api_key, model or settings.groq_model)

    def extra_body(self) -> dict:
        return {"reasoning_effort": settings.groq_reasoning_effort} if settings.groq_reasoning_effort else {}


class NvidiaLLM(OpenAICompatLLM):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    name = "nvidia"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        super().__init__(api_key or settings.nvidia_api_key, model or settings.nvidia_model)

    def extra_body(self) -> dict:
        return {"chat_template_kwargs": {"enable_thinking": settings.nvidia_enable_thinking}}


def get_llm() -> LLM:
    p = settings.llm_provider
    if p == "nvidia" or (p == "auto" and settings.nvidia_api_key):
        return NvidiaLLM()
    return GroqLLM()
