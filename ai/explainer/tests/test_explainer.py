"""Explainer tests: the model's words are shown only if every number and ID is backed by the Result."""

import json
from pathlib import Path

import pytest

from ai.explainer import explain, template_explanation, verify_text
from ai.fixer import ScriptedLLM
from contracts import Result, Scenario

FIXTURES = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"


def load(model, name):
    return model.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def scenario():
    return load(Scenario, "f1_scenario.json")


@pytest.fixture
def failing():
    return load(Result, "f1_result_fail.json")


def reply(headline="Order lost after capture", what="PayPal shows 1 capture of 38.97 USD, but the app recorded 0 captures.",
          impact="Buyer paid 38.97 USD without fulfillment."):
    return json.dumps({"headline": headline, "what_happened": what, "impact": impact})


def test_grounded_text_is_accepted(failing, scenario):
    out = explain(failing, scenario, ScriptedLLM([reply()]))
    assert out.source == "llm" and out.attempts == 1 and out.rejected == []
    assert "38.97" in out.what_happened


def test_known_ids_are_allowed(failing, scenario):
    what = "Order 5O190127TN364715T has capture 2GG6923447384114H."
    assert verify_text([what], failing, scenario) == []


def test_invented_number_is_rejected_then_retried(failing, scenario):
    llm = ScriptedLLM([reply(what="PayPal shows 3 captures totalling 116.91 USD."), reply()])
    out = explain(failing, scenario, llm)
    assert out.source == "llm" and out.attempts == 2
    assert "number 3 is not in the result" in llm.calls[1]["user"]  # the reason goes back to the model
    assert len(out.rejected) == 1


def test_invented_id_is_rejected(failing, scenario):
    problems = verify_text(["Capture 9ZZ1234567890123Q was created."], failing, scenario)
    assert problems == ["ID 9ZZ1234567890123Q is not in the result"]


def test_http_status_code_the_result_never_mentions_is_rejected(failing, scenario):
    assert verify_text(["The shop got a 504 and retried."], failing, scenario) == ["number 504 is not in the result"]


def test_fault_codes_and_ids_digits_are_not_read_as_numbers(failing, scenario):
    assert verify_text(["The F1 test f1-capture-lost-001 failed."], failing, scenario) == []


def test_decimals_compare_by_value(failing, scenario):
    assert verify_text(["Total captured was 38.970 USD."], failing, scenario) == []


def test_bad_json_is_retried(failing, scenario):
    out = explain(failing, scenario, ScriptedLLM(["The buyer was charged twice.", reply()]))
    assert out.source == "llm" and out.attempts == 2


def test_fenced_reply_is_accepted(failing, scenario):
    assert explain(failing, scenario, ScriptedLLM(["```json\n" + reply() + "\n```"])).source == "llm"


def test_falls_back_to_template_after_three_bad_attempts(failing, scenario):
    llm = ScriptedLLM([reply(what="Charged 99.99 USD.")] * 3)
    out = explain(failing, scenario, llm)
    assert out.source == "template" and out.attempts == 3 and len(out.rejected) == 3
    assert verify_text([out.headline, out.what_happened, out.impact], failing, scenario) == []


def test_follows_the_result_not_a_fixed_story(failing, scenario):
    """The corrected F1 story: PayPal has 1 capture, so '2 captures' must be refused."""
    paid_once = failing.model_copy(deep=True)
    paid_once.observed.captures = 1
    paid_once.observed.amount_captured = "38.97"
    paid_once.evidence.paypal_capture_ids = ["2GG6923447384114H"]
    paid_once.money_impact = "buyer paid 38.97 USD but the shop recorded no order"

    assert verify_text(["PayPal shows 1 capture of 38.97 USD."], paid_once, scenario) == []
    assert verify_text(["PayPal shows 2 captures."], paid_once, scenario) == ["number 2 is not in the result"]


def test_passing_result_needs_no_model(scenario):
    passing = load(Result, "f1_result_pass.json")
    llm = ScriptedLLM([])
    out = explain(passing, scenario, llm)
    assert out.source == "template" and llm.calls == []
    assert verify_text([out.headline, out.what_happened, out.impact], passing, scenario) == []