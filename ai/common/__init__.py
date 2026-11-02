"""DriftGuard Common AI utilities.

Shared LLM adapter, caching, and spend guarding across Role B and Role C.
"""

from .llm import LLMClient, LLMError, ScriptedLLM, extract_json
from .providers import (
    AnthropicClient,
    CachedLLM,
    FallbackLLM,
    GeminiClient,
    GroqClient,
    OfflineLLM,
    SpendGuard,
    cost_usd,
    llm_from_env,
)

__all__ = [
    "LLMClient",
    "LLMError",
    "ScriptedLLM",
    "extract_json",
    "GeminiClient",
    "GroqClient",
    "AnthropicClient",
    "SpendGuard",
    "FallbackLLM",
    "CachedLLM",
    "OfflineLLM",
    "cost_usd",
    "llm_from_env",
]

