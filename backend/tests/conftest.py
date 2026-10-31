import json
import pytest

from app import seed
from app.core.db import db
from app.llm import LLM, LLMError


@pytest.fixture(autouse=True)
def fresh_seed():
    with db() as d:
        seed.reset(d)


class ScriptedLLM(LLM):
    """Replays a fixed list of assistant messages; an Exception entry is raised as LLMError."""

    def __init__(self, script: list):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, tools):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise LLMError(str(item))
        return item


def call(name: str, **args) -> dict:
    return {"id": f"c-{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def msg(*calls: dict, content: str | None = None) -> dict:
    return {"content": content, "tool_calls": list(calls) or None}
