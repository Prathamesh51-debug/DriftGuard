"""LLM seam for the Fixer.

The team adapter (ai/common, owned by B) will implement LLMClient. Until it
lands the Fixer is tested with ScriptedLLM, so no API key is needed.
"""

from typing import List, Protocol


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return the model's raw text reply."""
        ...


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
