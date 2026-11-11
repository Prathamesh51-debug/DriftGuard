"""Provider tests: failover, spend guard, cache and reply parsing. Nothing here touches the network."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.fixer import providers
from ai.fixer.llm import LLMError, ScriptedLLM
from ai.fixer.providers import (
    AnthropicClient, CachedLLM, FallbackLLM, GeminiClient, GroqClient, SpendGuard, cost_usd, llm_from_env,
)


KNOWN_FIX = Path(__file__).resolve().parents[1] / "known_fixes" / "BUG-01.diff"


class Down:
    name = "down"

    def complete(self, system, user):
        raise LLMError("down: HTTP 429")


class Up:
    name = "up"

    def __init__(self, text="ok"):
        self.text, self.calls = text, 0

    def complete(self, system, user):
        self.calls += 1
        return self.text


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, json.dumps(body)

    def json(self):
        return self._body


def test_fallback_uses_first_working_provider():
    chain = FallbackLLM([Down(), Up("from second")])
    assert chain.complete("s", "u") == "from second" and chain.last_provider == "up"


def test_fallback_skips_later_providers_when_first_works():
    first, second = Up("a"), Up("b")
    assert FallbackLLM([first, second]).complete("s", "u") == "a" and second.calls == 0


def test_fallback_raises_when_all_fail():
    with pytest.raises(LLMError, match="all providers failed.*down: HTTP 429"):
        FallbackLLM([Down(), Down()]).complete("s", "u")


def test_gemini_reply_is_parsed_and_thought_parts_dropped(monkeypatch):
    body = {"candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": '{"a": 1}'}]}}]}
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers)
        return FakeResponse(200, body)

    monkeypatch.setattr(providers.requests, "post", fake_post)
    assert GeminiClient("KEY", "gemini-x").complete("sys", "usr") == '{"a": 1}'
    assert "KEY" not in seen["url"] and seen["headers"] == {"x-goog-api-key": "KEY"}  # key never goes in the URL


def test_groq_reply_is_parsed(monkeypatch):
    body = {"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}]}
    monkeypatch.setattr(providers.requests, "post", lambda *a, **k: FakeResponse(200, body))
    assert GroqClient("KEY").complete("s", "u") == "hello"


def test_http_error_and_empty_reply_become_llm_errors(monkeypatch):
    monkeypatch.setattr(providers.requests, "post", lambda *a, **k: FakeResponse(429, {"error": "quota"}))
    with pytest.raises(LLMError, match="HTTP 429"):
        GroqClient("KEY").complete("s", "u")
    monkeypatch.setattr(providers.requests, "post", lambda *a, **k: FakeResponse(200, {"candidates": []}))
    with pytest.raises(LLMError, match="empty reply"):
        GeminiClient("KEY").complete("s", "u")


def fake_anthropic(text="done", in_tokens=1000, out_tokens=500, stop="end_turn"):
    msg = SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop,
                          usage=SimpleNamespace(input_tokens=in_tokens, output_tokens=out_tokens))
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return msg

    return SimpleNamespace(messages=SimpleNamespace(create=create)), calls


def test_anthropic_sends_only_prompt_and_cap_and_records_spend(tmp_path):
    client, calls = fake_anthropic()
    guard = SpendGuard(1.50, tmp_path / "spend.json")
    assert AnthropicClient(model="claude-haiku-5-5", guard=guard, client=client).complete("sys", "usr") == "done"
    assert set(calls[0]) == {"model", "max_tokens", "system", "messages"}  # no temperature or other sampling settings
    assert guard.spent_usd == pytest.approx(0.00035)  # 1000 in x $0.10/M + 500 out x $0.50/M


def test_spend_guard_stops_paid_calls_and_persists(tmp_path):
    path = tmp_path / "spend.json"
    SpendGuard(1.0, path).add(1.0)
    client, calls = fake_anthropic()
    with pytest.raises(LLMError, match="spend limit"):
        AnthropicClient(guard=SpendGuard(1.0, path), client=client).complete("s", "u")
    assert calls == []  # no paid request was made
    chain = FallbackLLM([AnthropicClient(guard=SpendGuard(1.0, path), client=client), Up("free")])
    assert chain.complete("s", "u") == "free"  # falls through to the free provider


def test_anthropic_refusal_is_an_error(tmp_path):
    client, _ = fake_anthropic(stop="refusal")
    with pytest.raises(LLMError, match="declined"):
        AnthropicClient(client=client).complete("s", "u")


def test_cost_uses_model_price_and_long_prompt_rate():
    assert cost_usd("claude-haiku-5-5", 100_000, 0) == pytest.approx(0.01)  # $0.10/M up to 100K tokens
    assert cost_usd("claude-haiku-5-5", 200_000, 0) == pytest.approx(0.10)  # long-prompt rate: $0.50/M
    assert cost_usd("some-new-model", 1_000_000, 0) == pytest.approx(4.00)  # unknown models billed at the Opus rate


def test_cache_returns_saved_reply_without_calling_provider(tmp_path):
    inner = Up("fresh")
    cached = CachedLLM(inner, tmp_path)
    assert cached.complete("s", "u") == "fresh" and cached.complete("s", "u") == "fresh"
    assert inner.calls == 1
    assert CachedLLM(inner, tmp_path, salt="run-2").complete("s", "u") == "fresh" and inner.calls == 2


def test_llm_from_env_skips_providers_without_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")  # placeholder counts as missing
    monkeypatch.setenv("GROQ_API_KEY", "real-looking-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    chain = llm_from_env("anthropic,gemini,groq", cache=False)
    assert [c.name for c in chain.clients] == ["groq"]


def test_llm_from_env_errors_when_no_keys(monkeypatch):
    for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(LLMError, match="no usable provider"):
        llm_from_env("gemini,groq", cache=False)


def test_fixer_and_explainer_fall_back_when_every_provider_is_down():
    """No model at all: the Fixer uses the curated patch and the Explainer uses the template."""
    from ai.explainer import explain
    from ai.fixer import find_bug, load_bugs, propose_fix
    from contracts import Result, Scenario

    root = Path(__file__).resolve().parents[3]
    scenario = Scenario.model_validate_json((root / "contracts/fixtures/f1_scenario.json").read_text(encoding="utf-8"))
    failing = Result.model_validate_json((root / "contracts/fixtures/f1_result_fail.json").read_text(encoding="utf-8"))
    dead = FallbackLLM([Down(), Down()])

    fix = propose_fix(failing, scenario, find_bug(scenario, load_bugs()), root / "targets/demo-shop", dead,
                      known_fixes=[KNOWN_FIX])
    assert fix.applies and fix.source == "known_fix"

    out = explain(failing, scenario, dead)
    assert out.source == "template" and "No model available" in out.rejected[0]


def test_extract_json_tolerates_fences_trailing_text_and_raw_newlines():
    from ai.fixer.llm import extract_json

    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": "x"} Hope that helps!') == {"a": "x"}
    assert extract_json('{"diff": "line1\nline2"}') == {"diff": "line1\nline2"}  # raw newline inside a string
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_importing_providers_does_not_need_the_anthropic_sdk():
    """Teammates who never use Anthropic must not need the package installed."""
    import subprocess
    import sys

    code = "import sys, ai.fixer.providers; print('anthropic' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.stdout.strip() == "False", out.stderr


def test_offline_mode_uses_curated_patch_and_template():
    from ai.explainer import explain
    from ai.fixer import find_bug, load_bugs, propose_fix
    from contracts import Result, Scenario

    root = Path(__file__).resolve().parents[3]
    scenario = Scenario.model_validate_json((root / "contracts/fixtures/f1_scenario.json").read_text(encoding="utf-8"))
    failing = Result.model_validate_json((root / "contracts/fixtures/f1_result_fail.json").read_text(encoding="utf-8"))
    offline = llm_from_env("none")

    fix = propose_fix(failing, scenario, find_bug(scenario, load_bugs()), root / "targets/demo-shop", offline,
                      known_fixes=[KNOWN_FIX])
    assert fix.applies and fix.source == "known_fix" and fix.provider is None
    out = explain(failing, scenario, offline)
    assert out.source == "template" and out.provider is None


def test_outputs_record_which_provider_answered():
    from ai.explainer import explain
    from ai.fixer import find_bug, load_bugs, propose_fix
    from contracts import Result, Scenario

    root = Path(__file__).resolve().parents[3]
    scenario = Scenario.model_validate_json((root / "contracts/fixtures/f1_scenario.json").read_text(encoding="utf-8"))
    failing = Result.model_validate_json((root / "contracts/fixtures/f1_result_fail.json").read_text(encoding="utf-8"))
    good_diff = KNOWN_FIX.read_text(encoding="utf-8")
    chain = FallbackLLM([Down(), Up(json.dumps({"diff": good_diff, "explanation": "ok"}))])

    fix = propose_fix(failing, scenario, find_bug(scenario, load_bugs()), root / "targets/demo-shop", chain)
    assert fix.source == "llm" and fix.provider == "up"  # Down failed, Up answered

    chain = FallbackLLM([Down(), Up(json.dumps({"headline": "One capture recorded", "what_happened": "PayPal shows 1 capture of 38.97 USD, but the app recorded 0 captures.",
                                                "impact": "Buyer paid 38.97 USD without fulfillment."}))])
    assert explain(failing, scenario, chain).provider == "up"


def test_cache_reports_cache_as_the_provider(tmp_path):
    cached = CachedLLM(FallbackLLM([Up("x")]), tmp_path)
    cached.complete("s", "u")
    assert cached.last_provider == "up"
    cached.complete("s", "u")
    assert cached.last_provider == "cache"


def test_anthropic_client_disables_brotli_encoding():
    from ai.common.providers import anthropic_client

    client = anthropic_client("test-key")
    assert client.default_headers.get("Accept-Encoding") == "gzip, deflate"
