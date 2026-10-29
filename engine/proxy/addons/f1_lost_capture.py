"""
Fault F1: Lost Capture Response Injection Addon
Planner Ref: Part 6 (Phase 1: Vertical Slice) & Part 10 (Fault F1)

Mechanism:
1. Intercepts POST /v2/checkout/orders/{id}/capture.
2. Allows PayPal Sandbox to process and capture the money (HTTP 201).
3. Drops the 201 response and substitutes HTTP 504 Gateway Timeout.
4. Records both the real PayPal capture ID and the injected fault into JSONL.
"""

import os
import json
import time
import hashlib
from pathlib import Path
from mitmproxy import ctx, http

# Log path inside the container
LOG_DIR = Path("/home/mitmproxy/logs")
LOG_FILE = LOG_DIR / "proxy_traffic.jsonl"


class F1LostCapture:
    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def request(self, flow: http.HTTPFlow):
        """Inspect and log incoming requests."""
        # Calculate SHA-256 hash of the request body for tamper-proofing
        body_bytes = flow.request.content or b""
        flow.metadata["req_body_hash"] = hashlib.sha256(body_bytes).hexdigest()
        flow.metadata["start_time"] = time.time()

        # Check if F1 chaos injection is requested via header or env var
        fault_header = flow.request.headers.get("X-DriftGuard-Fault", "").upper()
        env_fault = os.getenv("DRIFTGUARD_FAULT", "").upper()

        is_capture = (
            flow.request.method == "POST"
            and "/v2/checkout/orders/" in flow.request.path
            and flow.request.path.endswith("/capture")
        )

        # Flag flow for F1 injection if criteria match
        if is_capture and (fault_header == "F1" or env_fault == "F1" or fault_header == "ALL"):
            flow.metadata["inject_f1"] = True
            ctx.log.warn(f"[F1 ARMED] Capture request detected on {flow.request.path}. Will drop response.")

    def response(self, flow: http.HTTPFlow):
        """Intercept response, log ground truth, and inject 504 drop."""
        duration_ms = int((time.time() - flow.metadata.get("start_time", time.time())) * 1000)
        req_id = flow.request.headers.get("PayPal-Request-Id", "NOT_SET")
        real_status = flow.response.status_code if flow.response else 0

        # Try to extract the real capture ID from PayPal's response before dropping it
        real_capture_id = None
        try:
            if flow.response and flow.response.content:
                res_json = json.loads(flow.response.content.decode("utf-8"))
                units = res_json.get("purchase_units", [])
                if units and "payments" in units[0]:
                    captures = units[0]["payments"].get("captures", [])
                    if captures:
                        real_capture_id = captures[0].get("id")
        except Exception:
            pass

        # Check if F1 chaos should be executed
        fault_injected = False
        if flow.metadata.get("inject_f1") and real_status in (200, 201):
            ctx.log.error(
                f"[F1 INJECTED] Real PayPal Capture: {real_capture_id or 'UNKNOWN'}. "
                f"Dropping HTTP {real_status} -> Injecting 504 Gateway Timeout."
            )

            # Drop the PayPal response and replace with simulated network failure
            flow.response = http.Response.make(
                504,
                json.dumps({
                    "error": "GATEWAY_TIMEOUT",
                    "message": "DriftGuard Injected Fault: F1 Lost Capture Response (HTTP 504)",
                    "injected_by": "DriftGuard Chaos Proxy"
                }).encode("utf-8"),
                {"Content-Type": "application/json"}
            )
            fault_injected = True

        # Append structured JSONL audit record
        audit_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": flow.request.method,
            "path": flow.request.path,
            "paypal_request_id": req_id,
            "request_body_hash": flow.metadata.get("req_body_hash"),
            "real_paypal_status": real_status,
            "real_capture_id": real_capture_id,
            "returned_status": flow.response.status_code if flow.response else 0,
            "fault_injected": "F1_LOST_CAPTURE" if fault_injected else None,
            "duration_ms": duration_ms
        }

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry) + "\n")
        except Exception as e:
            ctx.log.error(f"[AUDIT LOG ERROR] Failed to write JSONL: {e}")


addons = [F1LostCapture()]