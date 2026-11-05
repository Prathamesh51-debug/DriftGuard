"""
Tests for DriftGuard Contracts (Pydantic v2).
Ensures that all JSON fixtures parse, strict validation rules hold, and extra fields are forbidden.
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from contracts.models import (
    ApprovalResult,
    Evidence,
    Expectation,
    FaultType,
    InjectAction,
    ObservedState,
    Result,
    Scenario,
    TargetCall,
    Verdict,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_f1_scenario_fixture():
    fixture_path = FIXTURES_DIR / "f1_scenario.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    scenario = Scenario.model_validate(data)

    assert scenario.scenario_id == "f1-capture-lost-001"
    assert scenario.fault == FaultType.F1_LOST_CAPTURE_RESPONSE
    assert scenario.target_call.file == "src/checkout.ts"
    assert scenario.target_call.line == 88
    assert scenario.inject.action == "drop_response_after_upstream"
    assert scenario.expect.captures_per_purchase == 1
    assert scenario.expect.amount == "38.97"


def test_f1_result_fail_fixture():
    fixture_path = FIXTURES_DIR / "f1_result_fail.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    result = Result.model_validate(data)

    assert result.scenario_id == "f1-capture-lost-001"
    assert result.verdict == Verdict.FAIL
    assert result.observed.captures == 1
    assert result.observed.amount_captured == "38.97"
    assert result.observed.app_recorded_captures == 0
    assert len(result.evidence.paypal_order_ids) == 1
    assert "buyer charged" in result.money_impact


def test_f1_result_pass_fixture():
    fixture_path = FIXTURES_DIR / "f1_result_pass.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    result = Result.model_validate(data)

    assert result.scenario_id == "f1-capture-lost-001"
    assert result.verdict == Verdict.PASS
    assert result.observed.captures == 1
    assert result.observed.amount_captured == "38.97"
    assert result.observed.app_recorded_captures == 1
    assert "clean" in result.money_impact


def test_approval_result_model():
    res = ApprovalResult(
        approved=True,
        order_id="5O190127TN364715T",
        payer_id="PAYER123",
        return_url="http://localhost:3000/return?token=5O190127TN364715T&PayerID=PAYER123",
        duration_s=8.5,
    )
    assert res.approved is True
    assert res.order_id == "5O190127TN364715T"


def test_extra_fields_forbidden():
    """Rule: Extra unapproved fields in Scenario or Result must be rejected."""
    bad_scenario_data = {
      "scenario_id": "f1-test",
      "fault": "F1_LOST_CAPTURE_RESPONSE",
      "target_call": {"file": "a.ts", "line": 10},
      "inject": {"on": "POST", "action": "drop"},
      "expect": {"captures_per_purchase": 1},
      "unauthorized_field": "danger"
    }
    with pytest.raises(ValidationError):
        Scenario.model_validate(bad_scenario_data)


def test_invalid_decimal_amount_rejected():
    """Financial amounts must be strict valid decimal strings (never arbitrary text or floats)."""
    with pytest.raises(ValidationError):
        Expectation(captures_per_purchase=1, amount="invalid_num")

    with pytest.raises(ValidationError):
        ObservedState(captures=1, amount_captured="NaN")


def test_invalid_line_number_rejected():
    with pytest.raises(ValidationError):
        TargetCall(file="index.ts", line=0)


def test_phase_2_breadth_fixtures():
    """Validates that all Phase 2 fixtures (F2, F3, F4, F5, F6, F7) conform strictly to contracts."""
    for fault_key in ["f2", "f3", "f4", "f5", "f6", "f7"]:
        scenario_file = FIXTURES_DIR / f"{fault_key}_scenario.json"
        assert scenario_file.exists(), f"Missing {scenario_file}"
        scenario = Scenario.model_validate_json(scenario_file.read_text(encoding="utf-8"))
        assert scenario.scenario_id.startswith(fault_key)

        fail_file = FIXTURES_DIR / f"{fault_key}_result_fail.json"
        assert fail_file.exists(), f"Missing {fail_file}"
        fail_res = Result.model_validate_json(fail_file.read_text(encoding="utf-8"))
        assert fail_res.verdict == Verdict.FAIL

        pass_file = FIXTURES_DIR / f"{fault_key}_result_pass.json"
        assert pass_file.exists(), f"Missing {pass_file}"
        pass_res = Result.model_validate_json(pass_file.read_text(encoding="utf-8"))
        assert pass_res.verdict == Verdict.PASS


