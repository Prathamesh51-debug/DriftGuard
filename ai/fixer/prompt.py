"""Prompt for the Fixer. The model drafts a diff; code decides whether it is accepted."""

from typing import Optional

from contracts import Result, Scenario

from .bugs import BugEntry

SYSTEM_PROMPT = """You fix payment-handling bugs in a Node/TypeScript app that uses the PayPal server SDK.

You are given a failing chaos test: what PayPal's own records show, the bug entry, and the source file.
Reply with ONE JSON object and nothing else:
{"diff": "<unified diff>", "explanation": "<one or two plain sentences>"}

Rules for the diff:
- Smallest change that makes the safe behaviour true. No refactors, no formatting changes.
- Change only the file named in the bug entry. Paths are relative to the app root: --- a/src/checkout.ts / +++ b/src/checkout.ts.
- Include 3 lines of unchanged context around every change. Do not include the "NN| " line-number prefixes.
- Use only SDK options listed under SDK notes. Do not invent APIs.
"""

# Guidance per fault, checked against @paypal/paypal-server-sdk 2.0.0 typings through the
# APIMatic Context Plugin (Spike 5). Add an entry per fault as each fixer is proven.
SDK_NOTES = {
    "F1_LOST_CAPTURE_RESPONSE": (
        "ordersController.captureOrder({ id, prefer, paypalRequestId }) accepts paypalRequestId, which is "
        "sent as the PayPal-Request-Id header. PayPal treats repeat calls with the same id as one request, so "
        "a retry cannot capture twice. Derive the id from the order id (for example a sha256 of "
        "`capture-${orderId}`) so every retry of the same capture sends the same value."
    ),
}


def _numbered(source: str) -> str:
    return "\n".join(f"{i:>3}| {line}" for i, line in enumerate(source.split("\n"), start=1))


def build_user_prompt(
    result: Result,
    scenario: Scenario,
    bug: BugEntry,
    source: str,
    previous_error: Optional[str] = None,
) -> str:
    obs = result.observed
    parts = [
        f"## Failing test\n{scenario.description or scenario.fault.value}\n"
        f"Rule broken: {result.rule}\n"
        f"PayPal's records: {obs.captures} captures, {obs.amount_captured} {scenario.expect.currency} captured; "
        f"expected {scenario.expect.captures_per_purchase} capture(s) of {scenario.expect.amount}.\n"
        f"Impact: {result.money_impact}",
        f"## Bug entry\n{bug.id}: {bug.name}\nFile: {bug.file}, near line {bug.target_line}\n"
        f"Failure mode: {bug.failure_mode}\nSafe behaviour: {bug.safe_behavior}",
        f"## SDK notes\n{SDK_NOTES.get(bug.fault, 'None for this fault.')}",
        f"## Source of {bug.file}\n{_numbered(source)}",
    ]
    if previous_error:
        parts.append(f"## Your previous attempt was rejected\n{previous_error}\nFix that and reply again.")
    return "\n\n".join(parts)
