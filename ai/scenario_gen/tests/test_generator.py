"""
Tests for DriftGuard Scenario Generator (ai/scenario_gen).
Validates schema conformance against contracts/models.py,
Rule 1 deterministic expectation calculation, and fixture generation.
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from contracts.models import FaultType, Scenario
from ai.scenario_gen import (
    FAULT_TEMPLATES,
    ScenarioGenerator,
    calculate_expectation,
    export_scenario_fixtures,
)
from ai.common.llm import LLMClient


class ScriptedLLM(LLMClient):
    """Test LLM returning pre-scripted replies."""

    def __init__(self, reply: str):
        self.reply = reply
        self.calls = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


def test_generate_canonical_f1():
    scenario = ScenarioGenerator.generate_f1()
    assert scenario.scenario_id == "f1-capture-lost-001"
    assert scenario.fault == FaultType.F1_LOST_CAPTURE_RESPONSE
    assert scenario.expect.captures_per_purchase == 1
    assert scenario.expect.amount == "38.97"
    assert scenario.expect.currency == "USD"
    assert scenario.inject.action == "drop_response_after_upstream"


def test_generate_canonical_f2():
    scenario = ScenarioGenerator.generate_f2()
    assert scenario.scenario_id == "f2-order-timeout-001"
    assert scenario.fault == FaultType.F2_SLOW_PAYPAL
    assert scenario.inject.action == "delay"
    assert scenario.inject.delay_ms == 6000
    assert scenario.expect.captures_per_purchase == 1
    assert scenario.expect.amount == "38.97"


def test_generate_canonical_f3_zero_captures():
    scenario = ScenarioGenerator.generate_f3()
    assert scenario.scenario_id == "f3-capture-declined-001"
    assert scenario.fault == FaultType.F3_FORCED_DECLINE
    assert scenario.expect.captures_per_purchase == 0
    assert scenario.expect.amount == "0.00"
    assert "INSTRUMENT_DECLINED" in (scenario.inject.mock_header or "")


def test_generate_canonical_f4():
    scenario = ScenarioGenerator.generate_f4()
    assert scenario.scenario_id == "f4-duplicate-invoice-001"
    assert scenario.fault == FaultType.F4_DUPLICATE_INVOICE
    assert "DUPLICATE_INVOICE_ID" in (scenario.inject.mock_header or "")
    assert scenario.expect.captures_per_purchase == 1


def test_all_fault_types_generate_valid_scenario():
    for fault in FaultType:
        scenario = ScenarioGenerator.generate_scenario(fault)
        assert isinstance(scenario, Scenario)
        assert scenario.fault == fault
        assert scenario.expect.captures_per_purchase >= 0


def test_rule_1_code_decides_expectations():
    """Rule 1: AI cannot falsify expectation amounts or calculations."""
    exp = calculate_expectation(FaultType.F3_FORCED_DECLINE, amount="100.00")
    # For F3 decline, code strictly overrides amount to 0.00 and captures to 0
    assert exp.captures_per_purchase == 0
    assert exp.amount == "0.00"

    exp_f1 = calculate_expectation(FaultType.F1_LOST_CAPTURE_RESPONSE, amount="49.99")
    assert exp_f1.captures_per_purchase == 1
    assert exp_f1.amount == "49.99"


def test_propose_with_llm_valid_json():
    llm = ScriptedLLM(json.dumps({
        "description": "Adversarial delay on checkout creation",
        "inject_action": {"on": "POST /v2/checkout/orders", "action": "delay", "delay_ms": 7500}
    }))
    scenario = ScenarioGenerator.propose_with_llm(FaultType.F2_SLOW_PAYPAL, llm)
    assert scenario.description == "Adversarial delay on checkout creation"
    assert scenario.inject.delay_ms == 7500
    # Expectation is still enforced deterministically by code
    assert scenario.expect.captures_per_purchase == 1
    assert scenario.expect.amount == "38.97"


def test_propose_with_llm_malformed_json_fallback():
    llm = ScriptedLLM("Here is my attack proposal: not valid json at all")
    scenario = ScenarioGenerator.propose_with_llm(FaultType.F1_LOST_CAPTURE_RESPONSE, llm)
    assert scenario.fault == FaultType.F1_LOST_CAPTURE_RESPONSE
    assert scenario.scenario_id == "f1-capture-lost-001"
    assert scenario.expect.captures_per_purchase == 1


def test_export_scenario_fixtures(tmp_path):
    exported = export_scenario_fixtures(tmp_path)
    assert len(exported) == 7
    for p in exported:
        assert p.exists()
        raw = p.read_text(encoding="utf-8")
        parsed = Scenario.model_validate_json(raw)
        assert isinstance(parsed, Scenario)


def test_generate_canonical_f6():
    scenario = ScenarioGenerator.generate_f6()
    assert scenario.scenario_id == "f6-webhook-replay-001"
    assert scenario.fault == FaultType.F6_WEBHOOK_REPLAY
    assert scenario.expect.captures_per_purchase == 1
    assert scenario.inject.payload["mode"] == "duplicate"


def test_generate_canonical_f7():
    scenario = ScenarioGenerator.generate_f7()
    assert scenario.scenario_id == "f7-prompt-injection-001"
    assert scenario.fault == FaultType.F7_PROMPT_INJECTION
    assert scenario.expect.no_refund_issued is True
    assert scenario.inject.payload["attack_type"] == "direct_override"


def test_generate_canonical_f5():
    scenario = ScenarioGenerator.generate_f5()
    assert scenario.scenario_id == "f5-money-math-001"
    assert scenario.fault == FaultType.F5_MONEY_MATH_TRAP
    assert scenario.expect.amount == "38.96"
    assert scenario.expect.currency == "USD"
    assert scenario.expect.captures_per_purchase == 1
    assert scenario.inject.payload["expected_tax"] == "2.97"


def test_calculate_expected_total_precision():
    from ai.scenario_gen import calculate_expected_total
    # USD: subtotal 35.99, tax 8.25%, discount 5.00
    # 35.99 * 0.0825 = 2.969175 -> rounds to 2.97
    # 35.99 + 2.97 - 5.00 = 33.96
    total, tax, disc = calculate_expected_total("35.99", tax_rate="0.0825", discount="5.00", currency="USD")
    assert total == "33.96"
    assert tax == "2.97"
    assert disc == "5.00"

    # JPY: zero-decimal currency
    total_jpy, tax_jpy, _ = calculate_expected_total("3500", tax_rate="0.10", currency="JPY")
    assert total_jpy == "3850"
    assert "." not in total_jpy


