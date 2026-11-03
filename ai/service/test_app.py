"""Tests for the AI service with a fake Anthropic client: no network, no key, no spend."""

from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from ai.common.providers import SpendGuard
from ai.service.app import ModelBackend, app, get_backend


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
