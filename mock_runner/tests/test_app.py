"""Mock runner tests: endpoints work and every Result matches the contracts."""

import time

import pytest
from fastapi.testclient import TestClient

from contracts import Result, Verdict
from mock_runner import app as mock_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mock_app, "RUNNING_SECONDS", 0.0)
    return TestClient(mock_app.app)


def test_seeded_run_is_red_and_contract_valid(client):
    runs = client.get("/runs").json()
    assert runs and runs[0]["status"] == "complete"
    result = Result.model_validate(runs[0]["result"])
    assert result.verdict == Verdict.FAIL
    assert result.evidence.paypal_capture_ids


def test_launch_then_get(client):
    created = client.post("/runs")
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    got = client.get(f"/runs/{run_id}").json()
    assert Result.model_validate(got["result"]).verdict == Verdict.FAIL
    assert got["scenario"]["fault"] == "F1_LOST_CAPTURE_RESPONSE"


def test_rerun_turns_red_into_green(client):
    run_id = client.post("/runs").json()["run_id"]
    again = client.post(f"/runs/{run_id}/rerun").json()
    assert again["rerun_of"] == run_id
    assert Result.model_validate(again["result"]).verdict == Verdict.PASS


def test_running_state_hides_result(monkeypatch):
    monkeypatch.setattr(mock_app, "RUNNING_SECONDS", 60.0)
    client = TestClient(mock_app.app)
    run = client.post("/runs").json()
    assert run["status"] == "running" and run["result"] is None


def test_unknown_run_is_404(client):
    assert client.get("/runs/nope").status_code == 404
    assert client.post("/runs/nope/rerun").status_code == 404


def test_verify_fix_is_explicitly_a_sample_not_a_new_paypal_order(client):
    original = client.post("/runs").json()
    sample = client.post(f"/runs/{original['run_id']}/verify-fix").json()
    assert sample["mode"] == "sample"
    assert sample["result"]["verdict"] == "PASS"
    assert sample["fix"]["proposal"]["source"] == "known_fix"
    assert sample["fix"]["proposal"]["provider"] is None
    assert all(not value.startswith(("ORD-VERIFIED-", "CAP-VERIFIED-"))
               for key in ("paypal_order_ids", "paypal_capture_ids")
               for value in sample["result"]["evidence"][key])


def test_preview_answer_does_not_impersonate_claude(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    answer = client.post("/llm/messages", json={"messages": [{"role": "user", "content": "F5?"}]}).json()
    assert answer["model"] == "driftguard-preview"
    assert "no Claude call" in answer["content"][0]["text"]
    assert answer["usage"] == {"input_tokens": 0, "output_tokens": 0}


def test_generic_studio_prompt_does_not_assume_f1_or_selected_run(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    answer = client.post("/llm/messages", json={
        "messages": [{"role": "user", "content": "For the latest failed run, explain a safe fix based on its evidence."}]
    }).json()
    text = answer["content"][0]["text"]
    assert "not linked to the run row" in text
    assert "Fault F1" not in text


def test_paid_route_rejects_oversized_requests_without_a_model_call(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    monkeypatch.setenv("DRIFTGUARD_PUBLIC_AI_ENABLED", "1")
    response = client.post("/llm/messages", json={"messages": [{"role": "user", "content": "x" * 41_000}]})
    assert response.status_code == 413


def test_paid_route_reports_provider_failure_instead_of_canned_reply(client, monkeypatch):
    import httpx

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, *_args, **_kwargs):
            return type("Reply", (), {"status_code": 401})()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    monkeypatch.setenv("DRIFTGUARD_PUBLIC_AI_ENABLED", "1")
    monkeypatch.setattr(mock_app, "_ai_calls_total", 0)
    monkeypatch.setattr(httpx, "Client", FakeClient)
    response = client.post("/llm/messages", json={"messages": [{"role": "user", "content": "F1?"}]})
    assert response.status_code == 502
    assert "401" in response.json()["detail"]


def test_paid_route_uses_server_model_and_caps_output(client, monkeypatch):
    import httpx

    sent = {}

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, *_args, **kwargs):
            sent.update(kwargs["json"])
            return type("Reply", (), {"status_code": 200, "json": lambda self: {
                "id": "msg_real", "model": "claude-haiku-5-5", "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "model answer"}],
            }})()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    monkeypatch.setenv("DRIFTGUARD_PUBLIC_AI_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    monkeypatch.setattr(mock_app, "_ai_calls_total", 0)
    monkeypatch.setattr(httpx, "Client", FakeClient)
    answer = client.post("/llm/messages", json={
        "model": "claude-opus-5-5", "max_tokens": 100_000,
        "messages": [{"role": "user", "content": "Explain F1"}],
    }).json()
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["max_tokens"] == 2048
    assert answer["id"] == "msg_real"


def test_paid_route_stops_at_process_call_limit(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    monkeypatch.setenv("DRIFTGUARD_PUBLIC_AI_ENABLED", "1")
    monkeypatch.setattr(mock_app, "_ai_calls_total", mock_app.MAX_AI_CALLS_PER_PROCESS)
    response = client.post("/llm/messages", json={"messages": [{"role": "user", "content": "F1?"}]})
    assert response.status_code == 429


def test_paid_route_accept_encoding_header_and_x_forwarded_for_rate_limit(client, monkeypatch):
    import httpx

    captured_headers = {}

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, *_args, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            return type("Reply", (), {"status_code": 200, "json": lambda self: {
                "id": "msg_ok", "content": [{"type": "text", "text": "ok"}],
            }})()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    monkeypatch.setenv("DRIFTGUARD_PUBLIC_AI_ENABLED", "1")
    monkeypatch.setattr(mock_app, "_ai_calls_total", 0)
    mock_app._ai_calls_by_ip.clear()
    monkeypatch.setattr(httpx, "Client", FakeClient)

    # First request from 203.0.113.195 via X-Forwarded-For
    res = client.post(
        "/llm/messages",
        headers={"x-forwarded-for": "203.0.113.195, 10.0.0.1"},
        json={"messages": [{"role": "user", "content": "F1?"}]},
    )
    assert res.status_code == 200
    assert captured_headers.get("Accept-Encoding") == "gzip, deflate"
    assert "203.0.113.195" in mock_app._ai_calls_by_ip
    assert len(mock_app._ai_calls_by_ip["203.0.113.195"]) == 1

    # Simulate reaching IP limit
    for _ in range(mock_app.MAX_AI_CALLS_PER_IP_HOUR - 1):
        mock_app._ai_calls_by_ip["203.0.113.195"].append(time.monotonic())

    blocked = client.post(
        "/llm/messages",
        headers={"x-forwarded-for": "203.0.113.195"},
        json={"messages": [{"role": "user", "content": "F1?"}]},
    )
    assert blocked.status_code == 429

    # Another IP still works
    allowed = client.post(
        "/llm/messages",
        headers={"x-forwarded-for": "198.51.100.42"},
        json={"messages": [{"role": "user", "content": "F1?"}]},
    )
    assert allowed.status_code == 200

    # Empty or whitespace x-forwarded-for falls back safely without creating empty string key
    empty_fwd = client.post(
        "/llm/messages",
        headers={"x-forwarded-for": "   "},
        json={"messages": [{"role": "user", "content": "F1?"}]},
    )
    assert empty_fwd.status_code == 200
    assert "" not in mock_app._ai_calls_by_ip


def test_launch_run_supports_specific_faults_and_rejects_unknown(client):
    created = client.post("/runs", json={"fault": "F3_FORCED_DECLINE"})
    assert created.status_code == 201
    run = created.json()
    assert run["scenario"]["fault"] == "F3_FORCED_DECLINE"
    assert Result.model_validate(run["result"]).verdict == Verdict.FAIL

    bad = client.post("/runs", json={"fault": "F99_NONEXISTENT"})
    assert bad.status_code == 422
    assert "Unknown fault" in bad.json()["detail"]


