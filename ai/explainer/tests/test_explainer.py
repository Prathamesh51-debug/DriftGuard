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

def test_drift_between_paypal_and_the_app_reaches_the_prompt_and_the_template(failing, scenario):
    """F1 ground truth: PayPal captured once but the app recorded none."""
    from ai.explainer.prompt import build_user_prompt

    assert failing.observed.app_recorded_captures == 0
    assert "App's own records: 0 capture(s)" in build_user_prompt(failing, scenario)

    out = template_explanation(failing, scenario)
    assert "app has no record" in out.headline and "app's own records show 0" in out.what_happened
    assert verify_text([out.headline, out.what_happened, out.impact], failing, scenario) == []


def test_prompt_includes_refund_and_webhook_event_ids(failing, scenario):
    from ai.explainer.prompt import build_user_prompt

    failing_with_ids = failing.model_copy(deep=True)
    failing_with_ids.evidence.paypal_refund_ids = ["REF-1111"]
    failing_with_ids.evidence.webhook_event_ids = ["WH-2222"]
    prompt = build_user_prompt(failing_with_ids, scenario)
    assert "PayPal refund IDs: REF-1111" in prompt
    assert "Webhook event IDs: WH-2222" in prompt



def test_text_about_the_app_record_is_checked_like_any_other_figure(failing, scenario):
    good = "PayPal shows 1 capture of 38.97 USD, but the app recorded 0 captures."
    assert verify_text([good], failing, scenario) == []
    assert verify_text(["The app recorded 3 captures."], failing, scenario) == ["number 3 is not in the result"]


def test_declined_payment_template_does_not_claim_paypal_took_money():
    scenario = load(Scenario, "f3_scenario.json")
    failing = load(Result, "f3_result_fail.json")
    out = template_explanation(failing, scenario)
    assert "app recorded a payment PayPal did not confirm" in out.headline
    assert "PayPal took" not in " ".join((out.headline, out.what_happened))
    assert verify_text([out.headline, out.what_happened, out.impact], failing, scenario) == []


def test_fixture_delay_attached_to_ms_is_not_a_measured_result():
    scenario = load(Scenario, "f2_scenario.json")
    failing = load(Result, "f2_result_fail.json")
    assert "number 6000 is not in the result" in verify_text(
        ["The test delayed PayPal by 6000ms."], failing, scenario)


def test_synthetic_f4_response_cannot_be_described_as_real_collision():
    scenario = load(Scenario, "f4_scenario.json")
    failing = load(Result, "f4_result_fail.json")
    assert "PayPal duplicate-invoice collision is not evidenced by this result" in verify_text(
        ["PayPal detected a duplicate invoice ID collision."], failing, scenario)
