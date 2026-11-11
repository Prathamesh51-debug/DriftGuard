"""
LLM providers for the Fixer and Explainer.

Gemini and Groq are free and used while developing. Anthropic (Haiku 5.5) is paid, so it
sits behind a spend guard that stops calling it once the limit is reached. FallbackLLM
tries providers in order and moves on when one fails; the Fixer and Explainer then have
their own last resort (the curated patch, the template text) if every provider fails.

Only a system prompt, a user prompt and an output cap are sent. No temperature or other
sampling settings, because newer Claude models reject them.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional

import requests
from dotenv import load_dotenv

from .llm import LLMClient, LLMError

REPO_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = REPO_ROOT / "logs"  # git-ignored
load_dotenv(REPO_ROOT / ".env")

MAX_OUTPUT_TOKENS = 8192
TIMEOUT_S = 90
DEFAULT_MODELS = {
    "gemini": "gemini-flash-latest",  # alias: fixed names like gemini-2.5-flash get closed to new users
    "groq": "openai/gpt-oss-120b",
    "anthropic": "claude-haiku-5-5",
}
# USD per 1M tokens (input, output). Unknown models are billed at the Opus rate to stay on the safe side.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
HAIKU_LONG_PROMPT = (0.50, 2.50)  # Haiku 5.5 rate for prompts over 100K tokens


def _post(url: str, headers: dict, body: dict, provider: str) -> dict:
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=TIMEOUT_S)
    except requests.RequestException as exc:
        raise LLMError(f"{provider}: {type(exc).__name__}") from exc
    if resp.status_code != 200:
        raise LLMError(f"{provider}: HTTP {resp.status_code} {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise LLMError(f"{provider}: reply was not JSON") from exc


class GeminiClient:
    name = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_MODELS["gemini"]):
        self.api_key, self.model = api_key, model

    def complete(self, system: str, user: str) -> str:
        data = _post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": self.api_key},
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS},
            },
            self.name,
        )
        candidate = (data.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text.strip():
            raise LLMError(f"gemini: empty reply (finishReason={candidate.get('finishReason')})")
        return text


class GroqClient:
    name = "groq"

    def __init__(self, api_key: str, model: str = DEFAULT_MODELS["groq"]):
        self.api_key, self.model = api_key, model

    def complete(self, system: str, user: str) -> str:
        data = _post(
            "https://api.groq.com/openai/v1/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_completion_tokens": MAX_OUTPUT_TOKENS,
            },
            self.name,
        )
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        if not text.strip():
            raise LLMError(f"groq: empty reply (finish_reason={choice.get('finish_reason')})")
        return text


class SpendGuard:
    """Running total of paid spend, saved to disk so it survives restarts. Refuses calls past the limit."""

    def __init__(self, limit_usd: float, path: Path = LOGS_DIR / "llm_spend.json"):
        self.limit_usd, self.path = limit_usd, Path(path)

    @property
    def spent_usd(self) -> float:
        try:
            return float(json.loads(self.path.read_text(encoding="utf-8"))["spent_usd"])
        except (OSError, ValueError, KeyError):
            return 0.0

    def allow(self) -> bool:
        return self.spent_usd < self.limit_usd

    def add(self, usd: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"spent_usd": round(self.spent_usd + usd, 6)}), encoding="utf-8")


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, PRICES["claude-opus-5-5"])
    if model == "claude-haiku-5-5" and input_tokens > 100_000:
        price_in, price_out = HAIKU_LONG_PROMPT
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def _anthropic_errors() -> tuple:
    """The SDK's error classes. The SDK is imported lazily so teammates who never use Anthropic don't need it installed."""
    try:
        import anthropic
    except ImportError:  # only when a fake client is injected in tests
        return ()
    return (anthropic.APIError,)


def anthropic_client(api_key: Optional[str]):
    """Build an Anthropic SDK client that avoids Brotli responses.

    mitmproxy pins Brotli<=1.1.0, whose Decompressor.process rejects httpx2's output_buffer_limit kwarg.
    """
    import anthropic

    return anthropic.Anthropic(api_key=api_key, default_headers={"Accept-Encoding": "gzip, deflate"})


class AnthropicClient:
    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODELS["anthropic"],
                 guard: Optional[SpendGuard] = None, client=None):
        self.model, self.guard = model, guard
        if client is None:
            client = anthropic_client(api_key)
        self.client = client

    def complete(self, system: str, user: str) -> str:
        if self.guard and not self.guard.allow():
            raise LLMError(f"anthropic: spend limit ${self.guard.limit_usd:.2f} reached")
        try:
            msg = self.client.messages.create(
                model=self.model, max_tokens=MAX_OUTPUT_TOKENS, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except _anthropic_errors() as exc:  # connection, rate limit, auth and server errors all mean "try the next provider"
            raise LLMError(f"anthropic: {type(exc).__name__}: {str(exc)[:200]}") from exc
        if self.guard:
            self.guard.add(cost_usd(self.model, msg.usage.input_tokens, msg.usage.output_tokens))
        if msg.stop_reason == "refusal":
            raise LLMError("anthropic: the model declined the request")
        text = "".join(b.text for b in msg.content if b.type == "text")
        if not text.strip():
            raise LLMError(f"anthropic: empty reply (stop_reason={msg.stop_reason})")
        return text


class FallbackLLM:
    """Try each provider in order and return the first usable reply."""

    def __init__(self, clients: List[LLMClient]):
        self.clients = clients
        self.last_provider: Optional[str] = None

    def complete(self, system: str, user: str) -> str:
        failures = []
        for client in self.clients:
            try:
                text = client.complete(system, user)
            except LLMError as exc:
                failures.append(str(exc))
                continue
            self.last_provider = getattr(client, "name", type(client).__name__)
            return text
        raise LLMError("all providers failed: " + " | ".join(failures))


class CachedLLM:
    """Reuse the saved reply for an identical prompt, so repeat dev runs cost nothing.

    Not for pass-rate evals: a cached bad reply is replayed every time. Pass a different
    `salt` per run in those, or leave the cache off.
    """

    def __init__(self, inner: LLMClient, directory: Path = LOGS_DIR / "llm_cache", salt: str = ""):
        self.inner, self.directory, self.salt = inner, Path(directory), salt
        self.last_provider: Optional[str] = None

    def complete(self, system: str, user: str) -> str:
        key = hashlib.sha256(f"{self.salt}\0{system}\0{user}".encode("utf-8")).hexdigest()
        path = self.directory / f"{key}.txt"
        if path.is_file():
            self.last_provider = "cache"
            return path.read_text(encoding="utf-8")
        text = self.inner.complete(system, user)
        self.last_provider = getattr(self.inner, "last_provider", None)
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return text


class OfflineLLM:
    """No model at all (DRIFTGUARD_LLM=none). Every call fails, so the Fixer uses the curated patch and the Explainer the template."""

    name = "offline"
    last_provider = None

    def complete(self, system: str, user: str) -> str:
        raise LLMError("offline mode: DRIFTGUARD_LLM=none")


def _key(name: str) -> Optional[str]:
    value = os.getenv(name, "").strip()
    return None if not value or "your_" in value else value


def llm_from_env(order: Optional[str] = None, *, cache: Optional[bool] = None) -> LLMClient:
    """Build the provider chain from .env.

    DRIFTGUARD_LLM is a comma list, first is tried first: "gemini,groq" while developing (free),
    "anthropic,gemini,groq" for final runs and the demo, "none" to use no model at all.
    Providers without a key are skipped.
    Optional: GEMINI_MODEL, GROQ_MODEL, ANTHROPIC_MODEL, ANTHROPIC_SPEND_LIMIT_USD (default 1.50),
    DRIFTGUARD_LLM_CACHE=1.
    """
    order = order or os.getenv("DRIFTGUARD_LLM", "gemini,groq")
    if order.strip().lower() in ("none", "off", "offline"):
        return OfflineLLM()
    clients: List[LLMClient] = []
    for name in (n.strip().lower() for n in order.split(",") if n.strip()):
        if name == "gemini" and (key := _key("GEMINI_API_KEY")):
            clients.append(GeminiClient(key, os.getenv("GEMINI_MODEL") or DEFAULT_MODELS["gemini"]))
        elif name == "groq" and (key := _key("GROQ_API_KEY")):
            clients.append(GroqClient(key, os.getenv("GROQ_MODEL") or DEFAULT_MODELS["groq"]))
        elif name == "anthropic" and (key := _key("ANTHROPIC_API_KEY")):
            guard = SpendGuard(float(os.getenv("ANTHROPIC_SPEND_LIMIT_USD", "1.50")))
            clients.append(AnthropicClient(key, os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODELS["anthropic"], guard))
    if not clients:
        raise LLMError(f"no usable provider for DRIFTGUARD_LLM={order!r}: add a key to .env, or set DRIFTGUARD_LLM=none to run without a model")
    chain: LLMClient = FallbackLLM(clients)
    if cache if cache is not None else os.getenv("DRIFTGUARD_LLM_CACHE") == "1":
        chain = CachedLLM(chain)
    return chain
