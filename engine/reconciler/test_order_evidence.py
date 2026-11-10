"""Per-order PayPal figures must not be replaced by the shop's aggregate state."""

from types import SimpleNamespace
from pathlib import Path

from contracts import Scenario, Verdict
from engine.reconciler import reconcile as module


FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def _reconcile(monkeypatch, tmp_path, fault: str, captures: int, amount: str, app_order: dict):
    scenario = Scenario.model_validate_json((FIXTURES / f"{fault}_scenario.json").read_text())
    ledger = {
        "captures": [{"id": "capture-1"}] if captures else [],
        "capture_ids": ["capture-1"] if captures else [],
        "refunds": [], "refund_ids": [],
        "total_captured_amount": amount,
    }
    client = SimpleNamespace(get_order=lambda _id: {}, parse_order_ledger=lambda _raw: ledger)
    monkeypatch.setattr(module, "fetch_app_state", lambda _url: {
        "orders": [app_order, {"orderId": "older", "captureCount": 1}],
        "totalCapturesRecorded": 2,
        "totalCapturedAmount": "77.94",
        "totalRefundsIssued": 0,
    })
    return module.reconcile_order(scenario, "current", client=client,
                                  log_path=tmp_path / "empty-audit.jsonl")


def test_decline_keeps_paypal_zero_separate_from_false_app_success(monkeypatch, tmp_path):
    result = _reconcile(monkeypatch, tmp_path, "f3", 0, "0.00",
                        {"orderId": "current", "captureCount": 1})
    assert result.verdict == Verdict.FAIL
    assert result.observed.captures == 0
    assert result.observed.app_recorded_captures == 1
    assert result.observed.amount_captured == "0.00"


def test_this_orders_amount_ignores_older_shop_captures(monkeypatch, tmp_path):
    result = _reconcile(monkeypatch, tmp_path, "f4", 1, "38.97",
                        {"orderId": "current", "captureCount": 1})
    assert result.verdict == Verdict.PASS
    assert result.observed.captures == 1
    assert result.observed.amount_captured == "38.97"
    assert "deterministic cart-hashed" not in result.money_impact


def test_missing_order_does_not_use_unrelated_shop_count():
    assert module.extract_app_captures({"orders": [{"orderId": "older", "captureCount": 2}],
                                        "totalCapturesRecorded": 2}, "current") is None


def test_webhook_replay_fails_on_duplicate_event_without_inventing_paypal_captures():
    scenario = Scenario.model_validate_json((FIXTURES / "f6_scenario.json").read_text())
    ledger = {"captures": [{"id": "real-cap"}], "total_captured_amount": "38.97"}
    app = {
        "orders": [{"orderId": "current", "captureCount": 1}],
        "webhookEventsProcessed": ["WH-REPLAY-998877-current", "WH-REPLAY-998877-current"],
    }
    verdict, rule, impact, app_captures = module._verdict_f6(scenario, ledger, app, "current", [])
    assert verdict == Verdict.FAIL
    assert rule == "webhook_event_processed_once && app_recorded_captures == captures"
    assert app_captures == 1
    assert "PayPal" in impact and "1 capture" in impact


def test_webhook_replay_passes_when_event_is_processed_once():
    scenario = Scenario.model_validate_json((FIXTURES / "f6_scenario.json").read_text())
    ledger = {"captures": [{"id": "real-cap"}], "total_captured_amount": "38.97"}
    app = {
        "orders": [{"orderId": "current", "captureCount": 1}],
        "webhookEventsProcessed": ["WH-REPLAY-998877-current"],
    }
    verdict, _, _, _ = module._verdict_f6(scenario, ledger, app, "current", [])
    assert verdict == Verdict.PASS


def test_f7_reports_shop_refund_as_simulated_when_paypal_has_none():
    scenario = Scenario.model_validate_json((FIXTURES / "f7_scenario.json").read_text())
    ledger = {"refunds": []}
    app = {"refunds": [{"orderId": "current", "refundId": "shop-only", "amount": "500.00"}], "orders": []}
    verdict, _, impact, _ = module._verdict_f7(scenario, ledger, app, "current", [])
    assert verdict == Verdict.FAIL
    assert "simulated" in impact
    assert "no PayPal refund was issued" in impact


def test_f7_ignores_another_orders_shop_refund():
    scenario = Scenario.model_validate_json((FIXTURES / "f7_scenario.json").read_text())
    ledger = {"refunds": []}
    app = {"refunds": [{"orderId": "older", "refundId": "shop-only", "amount": "500.00"}], "orders": []}
    verdict, _, _, _ = module._verdict_f7(scenario, ledger, app, "current", [])
    assert verdict == Verdict.PASS


def test_f7_missing_shop_order_is_error_instead_of_false_pass(monkeypatch, tmp_path):
    scenario = Scenario.model_validate_json((FIXTURES / "f7_scenario.json").read_text())
    ledger = {"captures": [{"id": "capture-1"}], "capture_ids": ["capture-1"],
              "refunds": [], "refund_ids": [], "total_captured_amount": "38.97"}
    client = SimpleNamespace(get_order=lambda _id: {}, parse_order_ledger=lambda _raw: ledger)
    monkeypatch.setattr(module, "fetch_app_state", lambda _url: None)
    result = module.reconcile_order(scenario, "current", client=client,
                                    log_path=tmp_path / "empty-audit.jsonl")
    assert result.verdict == Verdict.ERROR


def test_f7_shop_refund_never_becomes_paypal_refund_evidence(monkeypatch, tmp_path):
    scenario = Scenario.model_validate_json((FIXTURES / "f7_scenario.json").read_text())
    ledger = {"captures": [{"id": "capture-1"}], "capture_ids": ["capture-1"],
              "refunds": [], "refund_ids": [], "total_captured_amount": "38.97"}
    client = SimpleNamespace(get_order=lambda _id: {}, parse_order_ledger=lambda _raw: ledger)
    monkeypatch.setattr(module, "fetch_app_state", lambda _url: {
        "orders": [{"orderId": "current", "captureCount": 1}],
        "refunds": [{"orderId": "current", "refundId": "shop-only", "amount": "500.00"}],
    })
    result = module.reconcile_order(scenario, "current", client=client,
                                    log_path=tmp_path / "empty-audit.jsonl")
    assert result.verdict == Verdict.FAIL
    assert result.observed.refunds_issued == 1
    assert result.evidence.paypal_refund_ids == []
