"""
Fault F2: Slow PayPal / Timeout on Order Creation.
Planner Ref: Part 10 (Fault Matrix) — F2 / BUG-02.

Mechanism:
  - Intercepts POST /v2/checkout/orders (order creation).
  - On Attempt 1: PayPal creates Order 1 (HTTP 201).
    Proxy injects timeout delay and returns HTTP 504 Gateway Timeout.
  - Target shop catches 504 and blindly retries without idempotency key (BUG-02).
  - On Attempt 2: PayPal creates Order 2 (HTTP 201).
    Proxy allows Attempt 2 to pass through.
  - Result: 2 orders created in PayPal for 1 user purchase.
    Reconciler detects duplicate orders in PayPal ground truth -> FAIL.
"""

import json
import time
from mitmproxy import ctx, http

DELAY_MS = int(1000)  # Simulated upstream gateway timeout delay

# Track time of last 504 injection so Attempt 1 vs Attempt 2 is tracked cleanly per run
_last_injection_time = 0.0


def _is_create_order(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.method == "POST"
        and flow.request.path.endswith("/v2/checkout/orders")
    )


def arm_request(flow: http.HTTPFlow):
    """Called by chaos_router on every request when F2 is active."""
    if _is_create_order(flow):
        flow.metadata["inject_f2"] = True


def inject_response(flow: http.HTTPFlow) -> bool:
    """
    Called by chaos_router on every response when F2 is active.
    Drops the first createOrder response with 504 to trigger client timeout & blind retry.
    """
    global _last_injection_time
    if not flow.metadata.get("inject_f2"):
        return False

    real_status = flow.response.status_code if flow.response else 0
    if real_status not in (200, 201):
        return False

    # Extract created order ID from PayPal upstream response
    real_order_id = None
    try:
        res_json = json.loads(flow.response.content.decode("utf-8"))
        real_order_id = res_json.get("id")
    except Exception:
        pass

    # Attach created order ID to flow metadata for the audit logger
    flow.metadata["real_order_id"] = real_order_id

    now = time.time()
    # If more than 15s elapsed since last injection, this is Attempt 1
    if (now - _last_injection_time) > 15.0:
        _last_injection_time = now
        ctx.log.error(
            f"[F2 INJECTED] Real PayPal Order Created: {real_order_id or 'UNKNOWN'}. "
            f"Injecting HTTP 504 Gateway Timeout to trigger client retry."
        )

        time.sleep(DELAY_MS / 1000.0)

        flow.response = http.Response.make(
            504,
            json.dumps({
                "error": "GATEWAY_TIMEOUT",
                "message": "DriftGuard Injected Fault: F2 Order Creation Timeout (HTTP 504)",
                "injected_by": "DriftGuard Chaos Proxy",
                "real_order_id": real_order_id,
            }).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        return True
    else:
        # Second attempt (retry) - let it through so flow can proceed to approval
        _last_injection_time = 0.0  # Reset for the next test run
        ctx.log.warn(
            f"[F2 RETRY ALLOWED] Retry request passed through. Order ID: {real_order_id}."
        )
        return False


