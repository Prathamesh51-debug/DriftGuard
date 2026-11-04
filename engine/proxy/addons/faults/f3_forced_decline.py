"""
Fault F3: Forced Decline (INSTRUMENT_DECLINED).
Planner Ref: Part 10 (Fault Matrix) — F3 / BUG-03.

Mechanism:
  - Intercepts POST /v2/checkout/orders/{id}/capture.
  - Injects `PayPal-Mock-Response: {"mock_application_codes": "INSTRUMENT_DECLINED"}`
    into the upstream request, forcing PayPal to return HTTP 422 UNPROCESSABLE_ENTITY.
  - If upstream returns 201 (e.g. sandbox mock header not honored), the proxy overrides
    it with PayPal's standard 422 INSTRUMENT_DECLINED payload.
  - Demo shop BUG-03: Catches 422 and erroneously marks order as COMPLETED, recording
    a capture locally even though the buyer was declined and NO money was captured.
  - DriftGuard Reconciler: Compares PayPal ledger (captures=0, $0.00) vs local app
    state (captures=1) -> FAIL (False Fulfillment / State Drift).
"""

import json
from mitmproxy import ctx, http

PAYPAL_422_DECLINE_BODY = {
    "name": "UNPROCESSABLE_ENTITY",
    "details": [
        {
            "issue": "INSTRUMENT_DECLINED",
            "description": "The instrument presented was declined by PayPal. (DriftGuard Fault F3)"
        }
    ],
    "message": "The requested action could not be performed, semantically incorrect, or failed business validation.",
    "debug_id": "driftguard-f3-decline-001",
    "links": [
        {
            "href": "https://developer.paypal.com/docs/api/orders/v2/#error-INSTRUMENT_DECLINED",
            "rel": "information_link",
            "method": "GET"
        }
    ]
}


def _is_capture(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.method == "POST"
        and "/v2/checkout/orders/" in flow.request.path
        and flow.request.path.endswith("/capture")
    )


def arm_request(flow: http.HTTPFlow):
    """
    Injects PayPal-Mock-Response header upstream so sandbox triggers real decline.
    """
    if _is_capture(flow):
        flow.metadata["inject_f3"] = True
        mock_val = json.dumps({"mock_application_codes": "INSTRUMENT_DECLINED"})
        flow.request.headers["PayPal-Mock-Response"] = mock_val
        ctx.log.warn(
            f"[F3 ARMED] Injected PayPal-Mock-Response: {mock_val} on {flow.request.path}"
        )


def inject_response(flow: http.HTTPFlow) -> bool:
    """
    Verifies 422 response. If PayPal didn't decline upstream, force 422 decline.
    """
    if not flow.metadata.get("inject_f3"):
        return False

    status = flow.response.status_code if flow.response else 0

    # If PayPal returned 422 as requested by mock header, mark fault injected
    if status == 422:
        ctx.log.error(f"[F3 OBSERVED] PayPal honored mock decline (HTTP 422).")
        return True

    # If PayPal returned 200/201 (ignored header), force 422 decline
    ctx.log.error(
        f"[F3 ENFORCED] Upstream returned HTTP {status}. Overriding to HTTP 422 INSTRUMENT_DECLINED."
    )
    flow.response = http.Response.make(
        422,
        json.dumps(PAYPAL_422_DECLINE_BODY).encode("utf-8"),
        {"Content-Type": "application/json"}
    )
    return True
