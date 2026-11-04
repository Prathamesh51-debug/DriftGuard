"""
Fault F1: Lost Capture Response.
Planner Ref: Part 10 (Fault Matrix) — F1 / BUG-01.

Mechanism:
  - Intercepts POST /v2/checkout/orders/{id}/capture.
  - Lets PayPal process and charge the buyer (HTTP 201).
  - Drops the 201 and substitutes HTTP 504 Gateway Timeout.
  - Demo shop retries without idempotency key → 422 ORDER_ALREADY_CAPTURED → records 0 captures.
  - DriftGuard reconciler detects: PayPal captures == 1, app captures == 0 → FAIL.
"""

import json
from mitmproxy import ctx, http


def _is_capture(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.method == "POST"
        and "/v2/checkout/orders/" in flow.request.path
        and flow.request.path.endswith("/capture")
    )


def arm_request(flow: http.HTTPFlow):
    """Called by chaos_router on every request when F1 is active."""
    if _is_capture(flow):
        flow.metadata["inject_f1"] = True
        ctx.log.warn(f"[F1 ARMED] Capture on {flow.request.path} — will drop 201 response.")


def inject_response(flow: http.HTTPFlow) -> bool:
    """
    Called by chaos_router on every response when F1 is active.
    Returns True if fault was injected (for audit log).
    """
    if not flow.metadata.get("inject_f1"):
        return False

    real_status = flow.response.status_code if flow.response else 0
    if real_status not in (200, 201):
        return False

    # Extract the real capture ID before we drop the response (for audit)
    real_capture_id = None
    try:
        res_json = json.loads(flow.response.content.decode("utf-8"))
        captures = res_json.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [])
        if captures:
            real_capture_id = captures[0].get("id")
    except Exception:
        pass

    ctx.log.error(
        f"[F1 INJECTED] Real PayPal capture: {real_capture_id or 'UNKNOWN'}. "
        f"Dropping HTTP {real_status} → 504 Gateway Timeout."
    )

    flow.response = http.Response.make(
        504,
        json.dumps({
            "error": "GATEWAY_TIMEOUT",
            "message": "DriftGuard Injected Fault: F1 Lost Capture Response (HTTP 504)",
            "injected_by": "DriftGuard Chaos Proxy",
            "real_capture_id": real_capture_id,
        }).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    return True

