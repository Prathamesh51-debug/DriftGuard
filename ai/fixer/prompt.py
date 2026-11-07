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
- The diff must be a standard unified diff, the format `git diff` prints: "--- a/src/checkout.ts", "+++ b/src/checkout.ts", then "@@ ... @@" hunks. Never use the "*** Begin Patch" format.
- Change only the file named in the bug entry. Paths are relative to the app root.
- Include 3 lines of unchanged context around every change. Do not include the "NN| " line-number prefixes.
- Use only SDK options listed under SDK notes. Do not invent APIs.
"""

# Guidance per fault, checked against @paypal/paypal-server-sdk 2.0.0 typings through the
# APIMatic Context Plugin (Spike 5). Add an entry per fault as each fixer is proven.
SDK_NOTES = {
    "F1_LOST_CAPTURE_RESPONSE": (
        "ordersController.captureOrder({ id, prefer, paypalRequestId }) accepts paypalRequestId, which is "
        "sent as the PayPal-Request-Id header. Derive it from the order id (for example a sha256 of "
        "`capture-${orderId}`) so retries of the same capture use the same value. After an ambiguous 504 or "
        "network error, first call ordersController.getOrder({ id: orderId }) and inspect its purchase-unit captures. "
        "If the order contains a COMPLETED capture, record that capture id and amount in the app and return success "
        "without retrying capture. Only retry with the same paypalRequestId when the status lookup shows no completed "
        "capture or the lookup itself fails. A lost response does not prove the capture failed; a retry alone is not "
        "enough to update the app's ledger."
    ),
    "F2_SLOW_PAYPAL": (
        "ordersController.createOrder({ body, prefer, paypalRequestId }) accepts paypalRequestId, which is "
        "sent as the PayPal-Request-Id header. When network timeouts or delays occur, retrying with the same "
        "deterministic paypalRequestId ensures PayPal idempotency: PayPal returns the existing order instead of "
        "creating duplicate orders. Derive paypalRequestId deterministically from the order parameters (for example "
        "crypto.createHash('sha256').update(`create-${amount}`).digest('hex')). Without it, a retry on timeout creates "
        "multiple unlinked orders in PayPal."
    ),
    "F3_FORCED_DECLINE": (
        "When ordersController.captureOrder returns HTTP 422 INSTRUMENT_DECLINED, the buyer's payment method was declined "
        "and $0 was captured by PayPal. The app must NOT treat 422 as completed or call recordCaptureSuccess. Instead, "
        "it must return failure (status: 'FAILED', success: false) so the order remains unpaid and the buyer is prompted "
        "to choose a different payment method. Erroneously recording capture success on 422 causes false fulfillment."
    ),
    "F4_DUPLICATE_INVOICE": (
        "In ordersController.createOrder, purchaseUnits[0].invoiceId must be deterministically derived from the order contents "
        "or cart (for example a hash of cart contents: `INV-${crypto.createHash('sha256').update(`cart-${amount}`).digest('hex').substring(0, 16).toUpperCase()}`) "
        "instead of using Math.random(). Random invoice IDs make reconciliation impossible and risk duplicate invoice collisions. "
        "Deterministic invoice IDs guarantee idempotent tracking across order attempts."
    ),
    "F5_MONEY_MATH_TRAP": (
        "In PayPal Orders v2, currency amounts must be calculated using integer minor units or strict Decimal "
        "arithmetic with exact rounding (e.g. ROUND_HALF_UP). Never perform raw IEEE 754 floating-point math "
        "for sales tax, discounts, or line-item totals, as truncation or precision errors cause amount drift and "
        "reconciliation failures. For zero-decimal currencies (such as JPY or KRW), amounts must never include "
        "fractional cents and must be formatted as whole integers."
    ),
    "F6_WEBHOOK_REPLAY": (
        "For BUG-09, keep the existing signature-validation flow and make event effects idempotent. "
        "shopState.hasWebhookEvent(event.id) checks whether the event was recorded; after payload validation but before "
        "ledger side effects, return HTTP 200 with status DUPLICATE_IGNORED when it is already present. "
        "The checkout capture endpoint may already have recorded a completed capture before its webhook arrives. "
        "For PAYMENT.CAPTURE.COMPLETED, derive orderId and only call recordCaptureSuccess when "
        "(shopState.getOrder(orderId)?.captureCount || 0) === 0. This demo models one full capture per order, so the "
        "webhook must not record a second local capture on top of the synchronous checkout result."
    ),
    "F7_PROMPT_INJECTION": (
        "In AI customer support workflows connected to payment tools, refund operations must never be triggered "
        "solely by unverified model responses or adversarial prompt text. Enforce deterministic policy guardrails "
        "in application code: enforce hard refund caps, verify authentication and admin authorization, and require "
        "human-in-the-loop review for exceptions rather than executing refunds directly from chat instructions."
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
        + (f"The app's own records show {obs.app_recorded_captures} capture(s).\n" if obs.app_recorded_captures is not None else "")
        +
        f"Impact: {result.money_impact}",
        f"## Bug entry\n{bug.id}: {bug.name}\nFile: {bug.file}, near line {bug.target_line}\n"
        f"Failure mode: {bug.failure_mode}\nSafe behaviour: {bug.safe_behavior}",
        f"## SDK notes\n{SDK_NOTES.get(bug.fault, 'None for this fault.')}",
        f"## Source of {bug.file}\n{_numbered(source)}",
    ]
    if previous_error:
        parts.append(f"## Your previous attempt was rejected\n{previous_error}\nFix that and reply again.")
    return "\n\n".join(parts)
