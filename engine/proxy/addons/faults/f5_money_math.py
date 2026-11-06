"""
Fault F5: Money Math Trap (fractional cent sales tax or coupon calculation drift).
Planner Ref: Part 10 (Fault Matrix) — F5 / BUG-05, BUG-06, BUG-07.

Mechanism:
  - Intercepts POST /v2/checkout/orders.
  - Monitors order creation payload for floating-point tax and discount rounding.
  - When demo shop calculates tax with float truncation (BUG-05), $0.04 is dropped:
    expected $38.96 USD, but shop requests $38.92 USD.
  - Proxy records the mutated order payload and tags the audit flow for ledger reconciliation.
  - Reconciler compares expected scenario amount with real PayPal captured ledger:
    Emits FAIL with exact calculated decimal drift:
    "money math drift: expected 38.96 USD, got 38.92 (-0.04 drift from floating-point tax rounding)".
"""

import json
from decimal import Decimal
from mitmproxy import ctx, http


def _is_order_create(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.method == "POST"
        and "/v2/checkout/orders" in flow.request.path
        and not flow.request.path.endswith("/capture")
    )


def arm_request(flow: http.HTTPFlow):
    """Called on POST /v2/checkout/orders when F5 is active."""
    if _is_order_create(flow):
        flow.metadata["inject_f5"] = True
        try:
            req_data = json.loads(flow.request.content.decode("utf-8"))
            purchase_unit = req_data.get("purchase_units", [{}])[0]
            val = purchase_unit.get("amount", {}).get("value")
            currency = purchase_unit.get("amount", {}).get("currency_code", "USD")
            ctx.log.warn(
                f"[F5 ARMED] Order creation intercepted. Requested amount: {val} {currency}. "
                f"Monitoring for fractional cent / tax decimal drift."
            )
        except Exception:
            ctx.log.warn("[F5 ARMED] Order creation intercepted for F5 money math verification.")


def inject_response(flow: http.HTTPFlow) -> bool:
    """
    Called on response when F5 is active.
    Extracts the created PayPal order ID and records audit evidence.
    Returns True to label fault_injected in the proxy audit log.
    """
    if not flow.metadata.get("inject_f5"):
        return False

    real_status = flow.response.status_code if flow.response else 0
    if real_status in (200, 201) and flow.response and flow.response.content:
        try:
            res_data = json.loads(flow.response.content.decode("utf-8"))
            order_id = res_data.get("id")
            purchase_unit = res_data.get("purchase_units", [{}])[0]
            val = purchase_unit.get("amount", {}).get("value")
            ctx.log.error(
                f"[F5 INJECTED] Order {order_id} recorded by PayPal with value: {val}. "
                f"Audit trail flagged for Reconciler decimal verification."
            )
        except Exception as e:
            ctx.log.warn(f"[F5] Could not parse order response: {e}")

    return True

