"""
DriftGuard Base Proxy Logger Addon
Planner Ref: Role Playbook A (A2 - Log PayPal-Request-Id & JSONL audit trail)
"""

import sys
from mitmproxy import ctx, http


class DriftGuardLogger:
    def request(self, flow: http.HTTPFlow):
        req_id = flow.request.headers.get("PayPal-Request-Id", "NOT_SET")
        msg = f"[DRIFTGUARD PROXY] -> {flow.request.method} {flow.request.path} | PayPal-Request-Id: {req_id}"
        # mitmproxy official event log
        ctx.log.info(msg)
        # Flush to container stdout so `docker logs` displays it immediately
        print(msg, flush=True)

    def response(self, flow: http.HTTPFlow):
        status = flow.response.status_code if flow.response else "NO_RESPONSE"
        msg = f"[DRIFTGUARD PROXY] <- {status} for {flow.request.method} {flow.request.path}"
        ctx.log.info(msg)
        print(msg, flush=True)


addons = [DriftGuardLogger()]
