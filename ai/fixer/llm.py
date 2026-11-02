"""LLM seam for the Fixer and Explainer.

Providers live in providers.py. The team adapter (ai/common, owned by B) can implement
LLMClient instead when it lands. Tests use ScriptedLLM, so no API key is needed.
"""

import json
from typing import List, Protocol


class LLMError(Exception):
    """The provider could not give a usable reply (rate limit, outage, bad key, spend limit)."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return the model's raw text reply. Raise LLMError if the provider fails."""
        ...


def extract_json(raw: str) -> dict:
    """First JSON object in a model reply. Tolerates code fences, text around it and raw newlines in strings."""
    text = raw.strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in the reply")
    obj, _ = json.JSONDecoder(strict=False).raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("reply JSON is not an object")
    return obj


class ScriptedLLM:
    """Replays canned replies in order and records what it was asked."""

    def __init__(self, replies: List[str]):
        self._replies = list(replies)
        self.calls: List[dict] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if not self._replies:
            raise RuntimeError("ScriptedLLM has no more replies")
        return self._replies.pop(0)
