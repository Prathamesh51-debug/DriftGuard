"""
Fault F4: Duplicate Invoice Collision.
Planner Ref: Part 10 (Fault Matrix) — F4 / BUG-04.

Mechanism:
  - Demo shop creates order with non-deterministic random invoice ID (BUG-04).
  - Target shop creates PayPal order successfully (HTTP 201).
  - On capture (POST .../capture), proxy injects a DUPLICATE_INVOICE_ID error (HTTP 409),
    simulating that PayPal detected an invoice ID collision against a previously settled order.
  - Demo shop capture fails; 0 captures recorded locally and in PayPal.
  - Reconciler checks expectation (captures_per_purchase == 1):
    Since invoice collision broke the purchase (captures == 0),
    Reconciler emits FAIL: "invoice collision: random invoice ID broke deterministic ledger reconciliation".
"""

import json
from mitmproxy import ctx, http

PAYPAL_409_DUP_INVOICE_BODY = {
    "name": "DUPLICATE_INVOICE_ID",
    "details": [
        {
            "issue": "DUPLICATE_INVOICE_ID",
            "description": "The requested invoice ID has already been paid in a previous transaction. (DriftGuard Fault F4)"
        }
    ],
    "message": "The invoice ID on this order has already been used on another settled transaction.",
    "debug_id": "driftguard-f4-dup-invoice-001"
}


def _is_capture(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.method == "POST"
        and "/v2/checkout/orders/" in flow.request.path
        and flow.request.path.endswith("/capture")
    )


def arm_request(flow: http.HTTPFlow):
    """Flag capture requests for F4 collision simulation."""
    if _is_capture(flow):
        flow.metadata["inject_f4"] = True
        ctx.log.warn(f"[F4 ARMED] Capture request detected on {flow.request.path} — will simulate invoice collision.")


def inject_response(flow: http.HTTPFlow) -> bool:
    """Override capture response with HTTP 409 DUPLICATE_INVOICE_ID."""
    if not flow.metadata.get("inject_f4"):
        return False

    ctx.log.error(
        "[F4 INJECTED] Simulating DUPLICATE_INVOICE_ID collision on capture (HTTP 409)."
    )
    flow.response = http.Response.make(
        409,
        json.dumps(PAYPAL_409_DUP_INVOICE_BODY).encode("utf-8"),
        {"Content-Type": "application/json"}
    )
    return True
