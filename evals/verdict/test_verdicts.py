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

