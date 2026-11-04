"""
DriftGuard Chaos Router — Unified mitmproxy Addon Entry Point.
Planner Ref: Role Playbook A (A2 - Fault-injection Proxy F1-F4).

Reads DRIFTGUARD_FAULT env var (or X-DriftGuard-Fault request header) and
dispatches request/response hooks to the matching fault handler.

Supported values:
  F1  — drop capture response after upstream 201 (lost capture)
  F2  — delay POST /v2/checkout/orders past app timeout (slow PayPal)
  F3  — mock INSTRUMENT_DECLINED 422 on capture (forced decline)
  F4  — mock DUPLICATE_INVOICE_ID 422 on order create (dup invoice)

All faults write a shared JSONL audit log at /home/mitmproxy/logs/proxy_traffic.jsonl.
"""

import hashlib
import json
import os
import time
from pathlib import Path
import importlib

from mitmproxy import ctx, http

# Fault handler modules — imported and reloaded dynamically so changes take effect immediately
from faults import f1_lost_capture, f2_slow_paypal, f3_forced_decline, f4_duplicate_invoice

LOG_DIR = Path("/home/mitmproxy/logs")
LOG_FILE = LOG_DIR / "proxy_traffic.jsonl"

HANDLERS = {
    "F1": f1_lost_capture,
    "F2": f2_slow_paypal,
    "F3": f3_forced_decline,
    "F4": f4_duplicate_invoice,
}


def _get_handler(fault: str):
    return HANDLERS.get(fault)


def _active_fault(flow: http.HTTPFlow) -> str:
    """Return the active fault code (env var takes precedence, header overrides per-request)."""
    header = flow.request.headers.get("X-DriftGuard-Fault", "").strip().upper()
    if header:
        return header
    return os.getenv("DRIFTGUARD_FAULT", "").strip().upper()


def _write_audit(entry: dict):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        ctx.log.error(f"[AUDIT LOG ERROR] {e}")


class ChaosRouter:
    def request(self, flow: http.HTTPFlow):
        # Fingerprint every request for the audit trail
        body_bytes = flow.request.content or b""
        flow.metadata["req_body_hash"] = hashlib.sha256(body_bytes).hexdigest()
        flow.metadata["start_time"] = time.time()

        fault = _active_fault(flow)
        handler = _get_handler(fault)
        if handler:
            handler.arm_request(flow)

    def response(self, flow: http.HTTPFlow):
        duration_ms = int((time.time() - flow.metadata.get("start_time", time.time())) * 1000)
        req_id = flow.request.headers.get("PayPal-Request-Id", "NOT_SET")
        real_status = flow.response.status_code if flow.response else 0

        fault = _active_fault(flow)
        handler = _get_handler(fault)
        fault_label = None
        if handler:
            injected = handler.inject_response(flow)
            if injected:
                fault_label = fault

        error_preview = None
        if real_status >= 400 and flow.response and flow.response.content:
            try:
                error_preview = flow.response.content.decode("utf-8")[:300]
            except Exception:
                pass

        # Shared JSONL audit entry — written for every PayPal API call
        audit_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "fault_active": fault or None,
            "method": flow.request.method,
            "path": flow.request.path,
            "paypal_request_id": req_id,
            "request_body_hash": flow.metadata.get("req_body_hash"),
            "real_paypal_status": real_status,
            "real_order_id": flow.metadata.get("real_order_id"),
            "error_preview": error_preview,
            "returned_status": flow.response.status_code if flow.response else 0,
            "fault_injected": fault_label,
            "duration_ms": duration_ms,
        }
        _write_audit(audit_entry)


addons = [ChaosRouter()]

