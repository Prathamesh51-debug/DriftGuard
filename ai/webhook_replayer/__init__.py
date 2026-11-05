"""
DriftGuard Webhook Replayer (Fault F6).
Generates and replays PayPal webhook events with adversarial mutations:
- Duplicate replay (idempotency attack)
- Unsigned webhook (signature bypass attack)
- Tampered payload (signature mismatch attack)
"""

from .replayer import (
    ReplayMode,
    WebhookEventPayload,
    WebhookReplayer,
    build_headers,
    build_webhook_payload,
)

__all__ = [
    "ReplayMode",
    "WebhookEventPayload",
    "WebhookReplayer",
    "build_headers",
    "build_webhook_payload",
]

