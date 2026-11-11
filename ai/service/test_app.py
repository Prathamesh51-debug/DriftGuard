"""Tests for the AI service with a fake Anthropic client: no network, no key, no spend."""

from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from ai.common.llm import ScriptedLLM
from ai.common.providers import OfflineLLM, SpendGuard
from ai.service.app import ModelBackend, app, get_backend, get_fix_llm, get_shop_dir


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.calls, self.reply, self.error = [], reply, error
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **body):
        self.calls.append(body)
        if self.error:
            raise self.error
        return self.reply


def reply(content, stop="end_turn", tokens=(100, 20)):
    def block(d):
        return SimpleNamespace(model_dump=lambda **_: dict(d))

    return SimpleNamespace(
        id="msg_1", model="claude-haiku-5-5", stop_reason=stop, content=[block(b) for b in content],
        usage=SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1]),
    )


@pytest.fixture
def make(tmp_path):
    def _make(client, limit=1.5):
        guard = SpendGuard(limit, tmp_path / "spend.json")
        app.dependency_overrides[get_backend] = lambda: ModelBackend(client, "claude-haiku-5-5", guard)
        return TestClient(app), guard

    yield _make
    app.dependency_overrides.clear()


ASK = {"messages": [{"role": "user", "content": "why did run 1 fail?"}], "system": "be brief"}


def test_returns_the_model_reply_and_records_spend(make):
    client = FakeClient(reply([{"type": "text", "text": "Because the retry had no idempotency key."}]))
    http, guard = make(client)
    out = http.post("/llm/messages", json=ASK).json()
    assert out["content"] == [{"type": "text", "text": "Because the retry had no idempotency key."}]
    assert out["usage"] == {"input_tokens": 100, "output_tokens": 20}
    assert guard.spent_usd > 0


def test_tool_use_blocks_pass_through(make):
    tool_use = {"type": "tool_use", "id": "tu_1", "name": "explain_run", "input": {"run_id": "r1"}}
    http, _ = make(FakeClient(reply([tool_use], stop="tool_use")))
    tool = {"name": "explain_run", "description": "d", "input_schema": {"type": "object"}}
    out = http.post("/llm/messages", json={**ASK, "tools": [tool]}).json()
    assert out["stop_reason"] == "tool_use" and out["content"] == [tool_use]


def test_the_server_picks_the_model_and_caps_output(make):
    client = FakeClient(reply([{"type": "text", "text": "ok"}]))
    http, _ = make(client)
    http.post("/llm/messages", json={**ASK, "max_tokens": 999_999, "model": "claude-opus-5-5"})
    assert client.calls[0]["model"] == "claude-haiku-5-5"
    assert client.calls[0]["max_tokens"] == 2048


def test_refuses_when_the_spend_limit_is_reached(make):
    client = FakeClient(reply([{"type": "text", "text": "ok"}]))
    http, guard = make(client, limit=0.01)
    guard.add(0.01)
    assert http.post("/llm/messages", json=ASK).status_code == 429
    assert client.calls == []


def test_refuses_oversized_requests_without_calling_the_model(make):
    client = FakeClient(reply([{"type": "text", "text": "ok"}]))
    http, _ = make(client)
    big = {"messages": [{"role": "user", "content": "x" * 250_000}]}
    assert http.post("/llm/messages", json=big).status_code == 413
    too_many = {**ASK, "tools": [{"name": f"t{i}", "description": "d", "input_schema": {}} for i in range(41)]}
    assert http.post("/llm/messages", json=too_many).status_code == 413
    assert client.calls == []


def test_a_provider_error_becomes_502_and_costs_nothing(make):
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    http, guard = make(FakeClient(error=err))
    resp = http.post("/llm/messages", json=ASK)
    assert resp.status_code == 502 and "APIConnectionError" in resp.json()["detail"]
    assert guard.spent_usd == 0


def test_no_key_gives_a_clear_503(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    app.dependency_overrides.clear()
    resp = TestClient(app).post("/llm/messages", json=ASK)
    assert resp.status_code == 503 and "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_health_reports_whether_a_model_is_ready(make):
    http, _ = make(FakeClient())
    body = http.get("/health").json()
    assert body["model_ready"] is True and body["spend_left_usd"] == 1.5


# --- POST /fix: the Fixer behind HTTP -------------------------------------------------------

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"
SCENARIO = json.loads((FIXTURES / "f1_scenario.json").read_text(encoding="utf-8"))
FAIL = json.loads((FIXTURES / "f1_result_fail.json").read_text(encoding="utf-8"))
PASS = json.loads((FIXTURES / "f1_result_pass.json").read_text(encoding="utf-8"))
GOOD_DIFF = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-01.diff").read_text(encoding="utf-8")


@pytest.fixture
def fixer():
    def _use(llm):
        app.dependency_overrides[get_fix_llm] = lambda: llm
        return TestClient(app)

    yield _use
    app.dependency_overrides.clear()


def test_fix_returns_a_checked_diff_from_the_model(fixer):
    llm = ScriptedLLM([json.dumps({"diff": GOOD_DIFF, "explanation": "Send a stable PayPal-Request-Id."})])
    out = fixer(llm).post("/fix", json={"scenario": SCENARIO, "result": FAIL}).json()
    assert out["applies"] is True and out["source"] == "llm" and out["bug_id"] == "BUG-01"
    assert out["files"] == ["src/checkout.ts"] and "paypalRequestId" in out["diff"]


def test_fix_falls_back_to_the_curated_patch_when_no_model_is_available(fixer):
    out = fixer(OfflineLLM()).post("/fix", json={"scenario": SCENARIO, "result": FAIL}).json()
    assert out["applies"] is True and out["source"] == "known_fix"


def test_fix_rejects_a_diff_that_does_not_apply_and_uses_the_curated_patch(fixer):
    bad_lines = ["diff --git a/src/checkout.ts b/src/checkout.ts", "--- a/src/checkout.ts", "+++ b/src/checkout.ts", "@@ -1,1 +1,1 @@", "-nope", "+nope2", ""]
    bad = json.dumps({"diff": chr(10).join(bad_lines)})
    out = fixer(ScriptedLLM([bad, bad, bad])).post("/fix", json={"scenario": SCENARIO, "result": FAIL}).json()
    assert out["source"] == "known_fix" and out["applies"] is True


def test_fix_refuses_a_run_that_did_not_fail(fixer):
    resp = fixer(OfflineLLM()).post("/fix", json={"scenario": SCENARIO, "result": PASS})
    assert resp.status_code == 422 and "PASS" in resp.json()["detail"]


def test_fix_says_so_when_the_bug_source_is_missing_from_the_shop(fixer, tmp_path):
    app.dependency_overrides[get_shop_dir] = lambda: tmp_path
    resp = fixer(OfflineLLM()).post("/fix", json={"scenario": SCENARIO, "result": FAIL})
    assert resp.status_code == 404 and "not seeded" in resp.json()["detail"]


def test_fix_never_edits_the_shop(fixer):
    shop_file = ROOT / "targets" / "demo-shop" / "src" / "checkout.ts"
    before = shop_file.read_bytes()
    fixer(OfflineLLM()).post("/fix", json={"scenario": SCENARIO, "result": FAIL})
    assert shop_file.read_bytes() == before


def test_get_backend_disables_brotli_encoding(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    backend = get_backend()
    assert backend is not None
    assert backend.client.default_headers.get("Accept-Encoding") == "gzip, deflate"

