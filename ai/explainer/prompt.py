"""Prompt for the Explainer. The model writes plain English; code checks every figure in it."""

from typing import Optional

from contracts import Result, Scenario

SYSTEM_PROMPT = """You explain failed payment tests to a developer in plain English.

You are given the facts from PayPal's own records. Reply with ONE JSON object and nothing else:
{"headline": "<under 12 words>", "what_happened": "<two or three sentences>", "impact": "<one sentence on the money or customer effect>"}

Rules:
- Use only numbers and IDs that appear in the facts. Do not invent, round or convert any figure.
- Do not mention HTTP status codes, retries, SDK names or code details unless the facts state them.
- Say what PayPal's records show compared with what was expected. Do not guess at causes beyond the facts.
- If the facts give the app's own records and they differ from PayPal's, say that PayPal took the payment but the app has no matching record.
- No markdown and no bullet points.
"""


def build_user_prompt(result: Result, scenario: Scenario, previous_error: Optional[str] = None) -> str:
    obs, ev = result.observed, result.evidence
    lines = [
        "## Facts",
        f"Test: {scenario.description or scenario.fault.value}",
        f"Verdict: {result.verdict.value}",
        f"Rule: {result.rule}",
        f"PayPal captures: {obs.captures}, total captured: {obs.amount_captured} {scenario.expect.currency}",
        *([f"App's own records: {obs.app_recorded_captures} capture(s)"] if obs.app_recorded_captures is not None else []),
        f"Expected: {scenario.expect.captures_per_purchase} capture(s), amount {scenario.expect.amount}",
        f"Orders created: {obs.orders_created}, refunds issued: {obs.refunds_issued}",
        f"Money impact (computed by code): {result.money_impact}",
        f"PayPal order IDs: {', '.join(ev.paypal_order_ids) or 'none'}",
        f"PayPal capture IDs: {', '.join(ev.paypal_capture_ids) or 'none'}",
    ]
    if result.error_message:
        lines.append(f"Error: {result.error_message}")
    if previous_error:
        lines += ["", "## Your previous answer was rejected", previous_error, "Fix that and reply again."]
    return "\n".join(lines)
