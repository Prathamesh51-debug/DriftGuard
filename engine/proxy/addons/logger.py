"""
DriftGuard Base Proxy Logger Addon
Planner Ref: Role Playbook A (A2 - Log PayPal-Request-Id & JSONL audit trail)
"""

import json
from mitmproxy import http


class DriftGuardLogger:
    def request(self, flow: http.HTTPFlow):
        req_id = flow.request.headers.get("PayPal-Request-Id", "NOT_SET")
        print(f"[DRIFTGUARD PROXY] -> {flow.request.method} {flow.request.path} | PayPal-Request-Id: {req_id}")

    def response(self, flow: http.HTTPFlow):
        status = flow.response.status_code if flow.response else "NO_RESPONSE"
        print(f"[DRIFTGUARD PROXY] <- {status} for {flow.request.method} {flow.request.path}")


addons = [DriftGuardLogger()]

