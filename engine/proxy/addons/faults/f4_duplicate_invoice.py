"""
Fault F4: Duplicate Invoice Collision.
Planner Ref: Part 10 (Fault Matrix) — F4 / BUG-04.

Mechanism:
  - Tracks invoice IDs across order creation and capture.
  - If an invoice ID is a duplicate of a previously settled invoice, or is non-deterministic / colliding,
    the proxy injects HTTP 409 DUPLICATE_INVOICE_ID on capture.
  - If the invoice ID is unique and deterministic, the capture proceeds cleanly (HTTP 201)
    and the invoice ID is recorded as settled.
"""

import json
import re
from typing import Dict, Set
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

_order_to_invoice: Dict[str, str] = {}
_colliding_orders: Set[str] = set()
_settled_invoices: Set[str] = set()


def _is_create_order(flow: http.HTTPFlow) -> bool:
    return flow.request.method == "POST" and flow.request.path.endswith("/v2/checkout/orders")


def _is_capture(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.method == "POST"
        and "/v2/checkout/orders/" in flow.request.path
        and flow.request.path.endswith("/capture")
    )


def _extract_order_id(path: str) -> str:
    parts = path.strip("/").split("/")
    return parts[-2] if len(parts) >= 2 and parts[-1] == "capture" else ""


def arm_request(flow: http.HTTPFlow):
    if _is_create_order(flow):
        try:
            body = json.loads(flow.request.content.decode("utf-8"))
            pu = (body.get("purchaseUnits") or body.get("purchase_units") or [{}])[0]
            invoice_id = pu.get("invoiceId") or pu.get("invoice_id") or ""
            flow.metadata["invoice_id"] = invoice_id

            # Collision: either invoice was already paid, or it's random/unstable
            if invoice_id in _settled_invoices or re.match(r"^INV-\d+$", invoice_id):
                flow.metadata["f4_collision"] = True
                if hasattr(ctx, "log") and hasattr(ctx.log, "warn"):
                    ctx.log.warn(f"[F4 DETECTED] Duplicate/unstable invoice ID collision: {invoice_id}")
        except Exception:
            pass

    elif _is_capture(flow):
        order_id = _extract_order_id(flow.request.path)
        if order_id in _colliding_orders or flow.metadata.get("f4_collision"):
            flow.metadata["inject_f4"] = True
            if hasattr(ctx, "log") and hasattr(ctx.log, "warn"):
                ctx.log.warn(f"[F4 ARMED] Injected collision on capture for order {order_id}")


def inject_response(flow: http.HTTPFlow) -> bool:
    if _is_create_order(flow):
        try:
            res = json.loads(flow.response.content.decode("utf-8"))
            order_id = res.get("id")
            invoice_id = flow.metadata.get("invoice_id")
            if order_id and invoice_id:
                _order_to_invoice[order_id] = invoice_id
                if flow.metadata.get("f4_collision"):
                    _colliding_orders.add(order_id)
        except Exception:
            pass
        return False

    if _is_capture(flow):
        order_id = _extract_order_id(flow.request.path)
        invoice_id = _order_to_invoice.get(order_id, flow.metadata.get("invoice_id"))

        if flow.metadata.get("inject_f4") or order_id in _colliding_orders:
            if hasattr(ctx, "log") and hasattr(ctx.log, "error"):
                ctx.log.error(f"[F4 INJECTED] Returning 409 DUPLICATE_INVOICE_ID for order {order_id}")
            flow.response = http.Response.make(
                409,
                json.dumps(PAYPAL_409_DUP_INVOICE_BODY).encode("utf-8"),
                {"Content-Type": "application/json"}
            )
            return True
        elif invoice_id and flow.response and flow.response.status_code in (200, 201):
            _settled_invoices.add(invoice_id)
            return False

    return False
