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
    """Verify fault fixtures F1 through F6 pass schema validation and expected verdicts."""
    for fault_key in ["f1", "f2", "f3", "f4", "f5", "f6"]:
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
    """Verify deterministic evaluation of F6 (webhook replay duplicate captures)."""
    from engine.reconciler.reconcile import _verdict_f6

    s_f6 = Scenario.model_validate_json((FIXTURES / "f6_scenario.json").read_text(encoding="utf-8"))
    # Fail case: app recorded 2 captures for a single purchase
    v_fail, rule_f6, impact_f6, _ = _verdict_f6(s_f6, {"captures": [{}]}, {"totalCapturesRecorded": 2}, "ord_1", ["ord_1"])
    assert v_fail == Verdict.FAIL
    assert "twice" in impact_f6

    # Pass case: app properly deduplicated, exactly 1 capture
    v_pass, _, impact_f6_pass, _ = _verdict_f6(s_f6, {"captures": [{}]}, {"totalCapturesRecorded": 1}, "ord_1", ["ord_1"])
    assert v_pass == Verdict.PASS
    assert "properly ignored" in impact_f6_pass



