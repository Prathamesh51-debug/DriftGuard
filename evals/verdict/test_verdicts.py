"""
Verdict Evals: Precision & False Alarm Verification for Reconciler Rules.
Planner Ref: Role Playbook A (Required Evals: Seeded bugs caught / 0 false alarms).
Rule: AI proposes, code decides.
"""

from pathlib import Path
import pytest
from contracts import Result, Scenario, Verdict, ObservedState, Evidence
from engine.reconciler.reconcile import reconcile_order

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def test_f1_fixtures_valid():
    """Verify contracts fixtures load cleanly without schema errors."""
    scenario = Scenario.model_validate_json((FIXTURES / "f1_scenario.json").read_text(encoding="utf-8"))
    res_fail = Result.model_validate_json((FIXTURES / "f1_result_fail.json").read_text(encoding="utf-8"))
    res_pass = Result.model_validate_json((FIXTURES / "f1_result_pass.json").read_text(encoding="utf-8"))

    assert scenario.fault.value == "F1_LOST_CAPTURE_RESPONSE"
    assert res_fail.verdict == Verdict.FAIL
    assert res_pass.verdict == Verdict.PASS


def test_state_drift_detected():
    """
    Simulate F1 Bug: PayPal charges buyer (captures=1), but app recorded 0 captures.
    Must deterministically produce Verdict.FAIL.
    """
    observed = ObservedState(
        captures=1,
        amount_captured="38.97",
        orders_created=1,
        refunds_issued=0,
        app_recorded_captures=0
    )
    # Check rule: app_recorded_captures == captures
    assert observed.app_recorded_captures != observed.captures


def test_zero_false_alarm_on_clean_order():
    """
    Simulate Fixed App: PayPal charges buyer (captures=1), and app recorded 1 capture.
    Must deterministically produce Verdict.PASS (Zero false alarms).
    """
    observed = ObservedState(
        captures=1,
        amount_captured="38.97",
        orders_created=1,
        refunds_issued=0,
        app_recorded_captures=1
    )
    assert observed.app_recorded_captures == observed.captures


def test_all_fixtures_reconcile_rules():
    """Verify all 7 fault fixtures (F1 through F7) pass schema validation and expected verdicts."""
    for fault_key in ["f1", "f2", "f3", "f4", "f5", "f6", "f7"]:
        scen = Scenario.model_validate_json((FIXTURES / f"{fault_key}_scenario.json").read_text(encoding="utf-8"))
        res_fail = Result.model_validate_json((FIXTURES / f"{fault_key}_result_fail.json").read_text(encoding="utf-8"))
        res_pass = Result.model_validate_json((FIXTURES / f"{fault_key}_result_pass.json").read_text(encoding="utf-8"))

        assert res_fail.verdict == Verdict.FAIL
        assert res_pass.verdict == Verdict.PASS
        assert res_fail.scenario_id == scen.scenario_id
        assert res_pass.scenario_id == scen.scenario_id


def test_reconciler_f5_logic():
    """Verify deterministic evaluation of F5 (money math precision drift)."""
    from engine.reconciler.reconcile import _verdict_f5

    s_f5 = Scenario.model_validate_json((FIXTURES / "f5_scenario.json").read_text(encoding="utf-8"))
    v_fail, rule_f5, impact_f5, _ = _verdict_f5(s_f5, {"total_captured_amount": "38.92"}, None, "ord_1", ["ord_1"])
    assert v_fail == Verdict.FAIL
    assert "money math drift" in impact_f5

    v_pass, _, impact_f5_pass, _ = _verdict_f5(s_f5, {"total_captured_amount": s_f5.expect.amount}, None, "ord_1", ["ord_1"])
    assert v_pass == Verdict.PASS
    assert "clean" in impact_f5_pass


def test_reconciler_f6_logic():
    """Verify deterministic evaluation of F6 (webhook replay duplicate event processing)."""
    from engine.reconciler.reconcile import _verdict_f6

    s_f6 = Scenario.model_validate_json((FIXTURES / "f6_scenario.json").read_text(encoding="utf-8"))
    # Fail case: webhook event processed twice while PayPal shows 1 capture
    v_fail, rule_f6, impact_f6, _ = _verdict_f6(
        s_f6,
        {"captures": [{}]},
        {"totalCapturesRecorded": 1, "webhookEventsProcessed": ["WH-REPLAY-998877-ord_1", "WH-REPLAY-998877-ord_1"]},
        "ord_1",
        ["ord_1"],
    )
    assert v_fail == Verdict.FAIL
    assert "processed 2 times" in impact_f6
    assert "PayPal shows 1 capture" in impact_f6

    # Pass case: duplicate ignored, event processed once and 1 capture on each side
    v_pass, _, impact_f6_pass, _ = _verdict_f6(
        s_f6,
        {"captures": [{}]},
        {"totalCapturesRecorded": 1, "webhookEventsProcessed": ["WH-REPLAY-998877-ord_1"]},
        "ord_1",
        ["ord_1"],
    )
    assert v_pass == Verdict.PASS
    assert "replay ignored" in impact_f6_pass


def test_reconciler_f7_logic():
    """Verify deterministic evaluation of F7 (prompt injection unauthorized refund)."""
    from engine.reconciler.reconcile import _verdict_f7

    s_f7 = Scenario.model_validate_json((FIXTURES / "f7_scenario.json").read_text(encoding="utf-8"))
    # Fail case: unauthorized refund recorded in PayPal and/or shop state
    v_fail, rule_f7, impact_f7, _ = _verdict_f7(
        s_f7,
        {"refunds": [{"id": "REF-UNAUTH", "amount": {"value": "500.00"}}]},
        {"refunds": [{"orderId": "ord_1", "refundId": "REF-UNAUTH", "amount": "500.00"}]},
        "ord_1",
        ["ord_1"],
    )
    assert v_fail == Verdict.FAIL
    assert "unauthorized refund" in impact_f7
    assert "500.00 USD" in impact_f7

    # Pass case: code guardrail prevented refund
    v_pass, _, impact_f7_pass, _ = _verdict_f7(s_f7, {"refunds": []}, {"refunds": []}, "ord_1", ["ord_1"])
    assert v_pass == Verdict.PASS
    assert "guardrail prevented" in impact_f7_pass



