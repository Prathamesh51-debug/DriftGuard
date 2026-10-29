"""
Tests for DriftGuard Contracts (Pydantic v2).
Ensures that all JSON fixtures parse, strict validation rules hold, and extra fields are forbidden.
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from contracts.models import (
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
    assert result.observed.captures == 2
    assert result.observed.amount_captured == "77.94"
    assert len(result.evidence.paypal_order_ids) == 1
    assert "buyer charged twice" in result.money_impact


def test_f1_result_pass_fixture():
    fixture_path = FIXTURES_DIR / "f1_result_pass.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    result = Result.model_validate(data)

    assert result.scenario_id == "f1-capture-lost-001"
    assert result.verdict == Verdict.PASS
    assert result.observed.captures == 1
    assert result.observed.amount_captured == "38.97"
    assert "clean" in result.money_impact


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

