"""
Fault F6: Webhook Replay & Duplicate Processing.
Planner Ref: Part 10 (Fault Matrix) — F6 / BUG-08, BUG-09.

Mechanism:
  - The runner sends the same capture event twice directly to the demo shop.
  - This proxy handler only logs webhook traffic when it is routed through the proxy.
  - The reconciler checks that the shop processed it once. PayPal still has
    one capture; a webhook replay does not charge the buyer again.
"""

import json
from mitmproxy import ctx, http


def _is_webhook(flow: http.HTTPFlow) -> bool:
    path = flow.request.path.lower()
    return (
        flow.request.method == "POST"
        and ("webhooks" in path or "notifications" in path)
    )


def arm_request(flow: http.HTTPFlow):
    """Flag webhook traffic for F6 replay audit."""
    if _is_webhook(flow):
        flow.metadata["inject_f6"] = True
        try:
            body = json.loads(flow.request.content.decode("utf-8"))
            event_id = body.get("id") or body.get("event_id", "UNKNOWN")
            event_type = body.get("event_type", "UNKNOWN")
            ctx.log.warn(
                f"[F6 ARMED] Webhook event intercepted: id={event_id}, type={event_type}. "
                f"Monitoring for duplicate event processing."
            )
        except Exception:
            ctx.log.warn("[F6 ARMED] Webhook request intercepted for F6 replay audit.")


def inject_response(flow: http.HTTPFlow) -> bool:
    """Audit webhook response and tag proxy traffic log."""
    if not flow.metadata.get("inject_f6"):
        return False

    status = flow.response.status_code if flow.response else 0
    ctx.log.error(
        f"[F6 OBSERVED] Webhook response HTTP {status}. Flagged for ledger reconciliation."
    )
    return True

