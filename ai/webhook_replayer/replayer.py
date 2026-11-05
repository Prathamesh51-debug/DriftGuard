"""
Webhook Replayer - Generates and injects adversarial PayPal webhook notifications.
Tests target endpoints for:
1. Missing signature verification (BUG-08)
2. Missing deduplication / idempotency (BUG-09)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, Field


class ReplayMode(str, Enum):
    DUPLICATE = "duplicate"
    UNSIGNED = "unsigned"
    TAMPERED = "tampered"


class WebhookEventPayload(BaseModel):
    id: str = Field(..., description="PayPal Webhook Event ID (WH-...)")
    event_version: str = "1.0"
    create_time: str
    event_type: str = "PAYMENT.CAPTURE.COMPLETED"
    resource_type: str = "capture"
    summary: str = "Payment capture completed"
    resource: Dict[str, Any]


def build_webhook_payload(
    event_id: Optional[str] = None,
    event_type: str = "PAYMENT.CAPTURE.COMPLETED",
    order_id: str = "ORDER-TEST-001",
    capture_id: Optional[str] = None,
    amount: str = "38.97",
    currency: str = "USD",
) -> Dict[str, Any]:
    """Build canonical PayPal Webhook Event JSON body."""
    eid = event_id or f"WH-{uuid.uuid4().hex[:16].upper()}"
    cid = capture_id or f"CAP-{uuid.uuid4().hex[:12].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "id": eid,
        "event_version": "1.0",
        "create_time": now_iso,
        "event_type": event_type,
        "resource_type": "capture",
        "summary": f"Payment capture completed for {amount} {currency}",
        "resource": {
            "id": cid,
            "status": "COMPLETED",
            "amount": {
                "value": str(amount),
                "currency_code": currency,
            },
            "supplementary_data": {
                "related_ids": {
                    "order_id": order_id,
                }
            },
            "create_time": now_iso,
            "update_time": now_iso,
        },
    }


def build_headers(
    mode: ReplayMode = ReplayMode.DUPLICATE,
    event_id: str = "WH-SAMPLE-EVENT",
    transmission_id: Optional[str] = None,
) -> Dict[str, str]:
    """Build HTTP headers tailored to the specific replay attack mode."""
    trans_id = transmission_id or str(uuid.uuid4())
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if mode == ReplayMode.UNSIGNED:
        # Omits transmission signature and cert-url (BUG-08 attack)
        return {
            "Content-Type": "application/json",
            "paypal-transmission-id": trans_id,
            "paypal-transmission-time": now_str,
        }

    if mode == ReplayMode.TAMPERED:
        # Provides invalid/tampered signature
        return {
            "Content-Type": "application/json",
            "paypal-transmission-id": trans_id,
            "paypal-transmission-time": now_str,
            "paypal-transmission-sig": "INVALID_SIGNATURE_TAMPERED_HASH_9999",
            "paypal-cert-url": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1234",
            "paypal-auth-algo": "SHA256withRSA",
        }

    # ReplayMode.DUPLICATE (Valid headers shape, used to test duplicate replay BUG-09)
    return {
        "Content-Type": "application/json",
        "paypal-transmission-id": trans_id,
        "paypal-transmission-time": now_str,
        "paypal-transmission-sig": f"SIG_{uuid.uuid4().hex}",
        "paypal-cert-url": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-LIVE",
        "paypal-auth-algo": "SHA256withRSA",
    }


class WebhookReplayer:
    """Client for executing webhook replay attacks against a target service."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:3001/api/webhooks",
        client: Optional[httpx.Client] = None,
    ):
        self.endpoint_url = endpoint_url
        self._client = client or httpx.Client(timeout=10.0)

    def send_event(
        self,
        payload: Dict[str, Any],
        mode: ReplayMode = ReplayMode.DUPLICATE,
        transmission_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a single webhook event with headers matching the replay mode."""
        headers = build_headers(mode=mode, event_id=payload.get("id", "WH-UNKNOWN"), transmission_id=transmission_id)
        response = self._client.post(self.endpoint_url, json=payload, headers=headers)
        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text}

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body,
            "mode": mode.value,
            "eventId": payload.get("id"),
        }

    def replay_duplicate(
        self,
        payload: Dict[str, Any],
        count: int = 2,
    ) -> List[Dict[str, Any]]:
        """Replay the identical event `count` times to probe for duplicate processing."""
        results = []
        for _ in range(count):
            res = self.send_event(payload, mode=ReplayMode.DUPLICATE)
            results.append(res)
        return results

    def replay_unsigned(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send event with missing transmission signature headers."""
        return self.send_event(payload, mode=ReplayMode.UNSIGNED)

    def replay_tampered(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send event with corrupted signature."""
        return self.send_event(payload, mode=ReplayMode.TAMPERED)

