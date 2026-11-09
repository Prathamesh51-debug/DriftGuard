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


def test_missing_order_does_not_use_unrelated_shop_count():
    assert module.extract_app_captures({"orders": [{"orderId": "older", "captureCount": 2}],
                                        "totalCapturesRecorded": 2}, "current") is None
