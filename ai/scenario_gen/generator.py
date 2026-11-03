"""
DriftGuard Scenario Generator (ai/scenario_gen/generator.py)
Planner Ref: Role Playbook B (B3 - Scenario Generator) & Day 8 (Tue 3 Nov).

Core Responsibilities:
1. Generates valid contracts.models.Scenario fixtures adhering to contracts/models.py.
2. Rule 1 ("AI proposes, code decides"):
   - Code calculates deterministic expectations (captures per purchase, expected amounts in USD).
   - If an LLM proposes edge cases or attack payloads, Python code strictly sanitizes, computes expectations,
     and validates the final Scenario structure against Pydantic models.
3. Provides canonical generators for F1 through F7 fault scenarios.
4. Exports scenario fixtures to contracts/fixtures/.
"""

from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from contracts.models import (
    Expectation,
    FaultType,
    InjectAction,
    Scenario,
    TargetCall,
)
from ai.common.llm import LLMClient


# Canonical fault configurations per fault matrix
FAULT_TEMPLATES: Dict[FaultType, Dict[str, Any]] = {
    FaultType.F1_LOST_CAPTURE_RESPONSE: {
        "scenario_id": "f1-capture-lost-001",
        "description": "Forward capture to PayPal sandbox, get 201 Created, kill response before app receives it to test blind retry",
        "target_call": {
            "file": "src/checkout.ts",
            "line": 88,
            "method": "OrdersController.captureOrder",
        },
        "inject": {
            "on": "POST .../capture",
            "action": "drop_response_after_upstream",
        },
        "expected_captures": 1,
        "default_amount": "38.97",
    },
    FaultType.F2_SLOW_PAYPAL: {
        "scenario_id": "f2-order-timeout-001",
        "description": "Inject 6000ms delay on POST /v2/checkout/orders to trigger client timeout and un-idempotent retry",
        "target_call": {
            "file": "src/checkout.ts",
            "line": 48,
            "method": "OrdersController.createOrder",
        },
        "inject": {
            "on": "POST .../v2/checkout/orders",
            "action": "delay",
            "delay_ms": 6000,
        },
        "expected_captures": 1,
        "default_amount": "38.97",
    },
    FaultType.F3_FORCED_DECLINE: {
        "scenario_id": "f3-capture-declined-001",
        "description": "Mock INSTRUMENT_DECLINED 422 response on POST .../capture to verify order is kept unpaid and not marked completed",
        "target_call": {
            "file": "src/checkout.ts",
            "line": 119,
            "method": "OrdersController.captureOrder",
        },
        "inject": {
            "on": "POST .../capture",
            "action": "mock_response",
            "mock_header": '{"mock_application_codes": "INSTRUMENT_DECLINED"}',
        },
        "expected_captures": 0,
        "default_amount": "0.00",
    },
    FaultType.F4_DUPLICATE_INVOICE: {
        "scenario_id": "f4-duplicate-invoice-001",
        "description": "Inject duplicate invoice ID collision to test deterministic cart hash invoice derivation",
        "target_call": {
            "file": "src/checkout.ts",
            "line": 48,
            "method": "OrdersController.createOrder",
        },
        "inject": {
            "on": "POST .../v2/checkout/orders",
            "action": "mock_response",
            "mock_header": '{"mock_application_codes": "DUPLICATE_INVOICE_ID"}',
        },
        "expected_captures": 1,
        "default_amount": "38.97",
    },
    FaultType.F5_MONEY_MATH_TRAP: {
        "scenario_id": "f5-money-math-001",
        "description": "Inject fractional cent sales tax or coupon calculation to trigger decimal drift",
        "target_call": {
            "file": "src/checkout.ts",
            "line": 48,
            "method": "OrdersController.createOrder",
        },
        "inject": {
            "on": "POST .../v2/checkout/orders",
            "action": "payload_mutation",
        },
        "expected_captures": 1,
        "default_amount": "38.97",
    },
    FaultType.F6_WEBHOOK_REPLAY: {
        "scenario_id": "f6-webhook-replay-001",
        "description": "Replay duplicate PAYMENT.CAPTURE.COMPLETED webhook event to verify idempotent ledger processing",
        "target_call": {
            "file": "src/webhooks.ts",
            "line": 25,
            "method": "WebhooksController.handleWebhook",
        },
        "inject": {
            "on": "POST /api/webhooks",
            "action": "replay_event",
        },
        "expected_captures": 1,
        "default_amount": "38.97",
    },
    FaultType.F7_PROMPT_INJECTION: {
        "scenario_id": "f7-prompt-injection-001",
        "description": "Inject adversarial prompt into AI shop assistant requesting unverified full refund",
        "target_call": {
            "file": "src/assistant.ts",
            "line": 30,
            "method": "AssistantController.processMessage",
        },
        "inject": {
            "on": "POST /api/chat",
            "action": "prompt_injection",
        },
        "expected_captures": 1,
        "default_amount": "38.97",
        "no_refund_issued": True,
    },
}


def calculate_expectation(
    fault: FaultType,
    amount: Optional[str] = None,
    currency: str = "USD",
) -> Expectation:
    """
    Rule 1 ('AI proposes, code decides'):
    Calculates deterministic expectations strictly in code using Decimal math.
    A language model never computes amounts or expected captures.
    """
    tmpl = FAULT_TEMPLATES.get(fault, {})
    expected_captures = tmpl.get("expected_captures", 1)

    if fault == FaultType.F3_FORCED_DECLINE:
        amt = "0.00"
    else:
        amt = amount if amount is not None else tmpl.get("default_amount", "38.97")
        d = Decimal(amt)
        amt = f"{d:.2f}"

    no_refund = tmpl.get("no_refund_issued")
    return Expectation(
        captures_per_purchase=expected_captures,
        amount=amt,
        currency=currency,
        no_refund_issued=no_refund,
    )


class ScenarioGenerator:
    """
    Builds and validates DriftGuard Scenario instances according to contracts/models.py.
    """

    @classmethod
    def generate_scenario(
        cls,
        fault: Union[FaultType, str],
        scenario_id: Optional[str] = None,
        description: Optional[str] = None,
        target_file: Optional[str] = None,
        target_line: Optional[int] = None,
        target_method: Optional[str] = None,
        amount: Optional[str] = None,
        currency: str = "USD",
        inject_override: Optional[Dict[str, Any]] = None,
    ) -> Scenario:
        """
        Generate a fully validated Scenario object.
        Deterministic code computes expectation; input parameters are strictly validated.
        """
        if isinstance(fault, str):
            fault = FaultType(fault)

        tmpl = FAULT_TEMPLATES.get(fault)
        if not tmpl:
            raise ValueError(f"Unknown fault type: {fault}")

        sid = scenario_id or tmpl["scenario_id"]
        desc = description or tmpl["description"]

        call_data = tmpl["target_call"]
        target_call = TargetCall(
            file=target_file or call_data["file"],
            line=target_line if target_line is not None else call_data["line"],
            method=target_method or call_data.get("method"),
        )

        inject_data = dict(tmpl["inject"])
        if inject_override:
            inject_data.update(inject_override)
        inject = InjectAction(**inject_data)

        # Code decides expectation!
        expect = calculate_expectation(fault, amount=amount, currency=currency)

        return Scenario(
            scenario_id=sid,
            fault=fault,
            description=desc,
            target_call=target_call,
            inject=inject,
            expect=expect,
        )

    @classmethod
    def generate_f1(cls, **kwargs) -> Scenario:
        return cls.generate_scenario(FaultType.F1_LOST_CAPTURE_RESPONSE, **kwargs)

    @classmethod
    def generate_f2(cls, **kwargs) -> Scenario:
        return cls.generate_scenario(FaultType.F2_SLOW_PAYPAL, **kwargs)

    @classmethod
    def generate_f3(cls, **kwargs) -> Scenario:
        return cls.generate_scenario(FaultType.F3_FORCED_DECLINE, **kwargs)

    @classmethod
    def generate_f4(cls, **kwargs) -> Scenario:
        return cls.generate_scenario(FaultType.F4_DUPLICATE_INVOICE, **kwargs)

    @classmethod
    def propose_with_llm(
        cls,
        fault: Union[FaultType, str],
        llm: LLMClient,
        context: Optional[str] = None,
    ) -> Scenario:
        """
        AI proposes variations or attack edge cases, CODE decides verdict & expectation.
        The LLM proposal is parsed and sanitized; expectations are enforced strictly by code.
        """
        if isinstance(fault, str):
            fault = FaultType(fault)

        system_prompt = (
            "You are a payment chaos engineering assistant for PayPal integrations. "
            "Suggest an attack scenario description and injection parameters for testing resilience. "
            "Reply with a JSON object containing: 'description' and optional 'inject_action'."
        )
        user_prompt = f"Fault: {fault.value}\nContext: {context or 'standard demo shop checkout'}"

        try:
            reply = llm.complete(system_prompt, user_prompt)
            data = json.loads(reply)
            desc = data.get("description")
            inject_override = data.get("inject_action") if isinstance(data.get("inject_action"), dict) else None
        except Exception:
            desc = None
            inject_override = None

        # Python code decides all expectations and structures:
        return cls.generate_scenario(
            fault=fault,
            description=desc,
            inject_override=inject_override,
        )


def export_scenario_fixtures(output_dir: Path) -> List[Path]:
    """
    Exports canonical scenario fixtures for F1, F2, F3, F4 to the contracts/fixtures directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = []

    scenarios = [
        ScenarioGenerator.generate_f1(),
        ScenarioGenerator.generate_f2(),
        ScenarioGenerator.generate_f3(),
        ScenarioGenerator.generate_f4(),
    ]

    for s in scenarios:
        prefix = s.fault.value[:2].lower()
        path = output_dir / f"{prefix}_scenario.json"
        path.write_text(s.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
        exported.append(path)

    return exported
