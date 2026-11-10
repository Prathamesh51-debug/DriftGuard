"""Fault inputs must exercise the seeded shop bug without inventing PayPal effects."""

from pathlib import Path

import pytest

from contracts import Scenario
from engine.orchestrator.runner import _action_prompt_injection, _action_replay_event, order_request_body


FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def scenario(fault: str) -> Scenario:
    return Scenario.model_validate_json((FIXTURES / f"{fault}_scenario.json").read_text())


def test_f5_sends_subtotal_without_using_expected_capture_as_input():
    body = order_request_body(scenario("f5"))
    assert body["subtotal"] == "35.99"
    assert body["tax_rate"] == "0.0825"
    assert "amount" not in body


def test_f3_still_creates_a_positive_order_before_forced_decline():
    assert order_request_body(scenario("f3"))["amount"] == "38.97"


def test_f6_replays_the_actual_capture_for_this_order(monkeypatch):
    import ai.webhook_replayer as module

    captured = {}

    class Replayer:
        def __init__(self, endpoint_url):
            captured["endpoint"] = endpoint_url

        def replay_duplicate(self, body, count):
            captured["body"] = body
            return [{"status_code": 200} for _ in range(count)]

    monkeypatch.setattr(module, "WebhookReplayer", Replayer)
    _action_replay_event(scenario("f6"), {
        "shop_base": "http://127.0.0.1:3001", "order_id": "REAL-ORDER", "capture_id": "REAL-CAPTURE",
    })
    assert captured["body"]["id"] == "WH-REPLAY-998877-REAL-ORDER"
    assert captured["body"]["resource"]["id"] == "REAL-CAPTURE"


def test_f6_refuses_to_replay_without_a_real_capture():
    with pytest.raises(RuntimeError, match="real capture ID"):
        _action_replay_event(scenario("f6"), {
            "shop_base": "http://127.0.0.1:3001", "order_id": "REAL-ORDER",
        })


def test_f7_reports_a_failed_injection_as_error(monkeypatch):
    import requests

    class FailedResponse:
        def raise_for_status(self):
            raise requests.HTTPError("shop returned 503")

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: FailedResponse())
    with pytest.raises(requests.HTTPError, match="503"):
        _action_prompt_injection(scenario("f7"), {
            "shop_base": "http://127.0.0.1:3001", "order_id": "REAL-ORDER",
        })
