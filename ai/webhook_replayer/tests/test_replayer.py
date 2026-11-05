"""Tests for Webhook Replayer."""

import httpx
import pytest

from ai.webhook_replayer.replayer import (
    ReplayMode,
    WebhookReplayer,
    build_headers,
    build_webhook_payload,
)


def test_build_webhook_payload_defaults():
    payload = build_webhook_payload(order_id="ORDER-123", amount="49.99")
    assert payload["id"].startswith("WH-")
    assert payload["event_type"] == "PAYMENT.CAPTURE.COMPLETED"
    assert payload["resource"]["amount"]["value"] == "49.99"
    assert payload["resource"]["amount"]["currency_code"] == "USD"
    assert payload["resource"]["supplementary_data"]["related_ids"]["order_id"] == "ORDER-123"


def test_build_headers_unsigned():
    headers = build_headers(mode=ReplayMode.UNSIGNED, event_id="WH-123")
    assert "paypal-transmission-sig" not in headers
    assert "paypal-cert-url" not in headers
    assert "paypal-transmission-id" in headers
    assert "paypal-transmission-time" in headers


def test_build_headers_tampered():
    headers = build_headers(mode=ReplayMode.TAMPERED, event_id="WH-123")
    assert headers["paypal-transmission-sig"] == "INVALID_SIGNATURE_TAMPERED_HASH_9999"
    assert "paypal-cert-url" in headers
    assert "paypal-auth-algo" in headers


def test_build_headers_duplicate():
    headers = build_headers(mode=ReplayMode.DUPLICATE, event_id="WH-123")
    assert "paypal-transmission-sig" in headers
    assert headers["paypal-transmission-sig"].startswith("SIG_")
    assert "paypal-cert-url" in headers
    assert "paypal-auth-algo" in headers


def test_webhook_replayer_with_mock_client():
    calls = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "paypal-transmission-sig" not in request.headers:
            return httpx.Response(401, json={"error": "INVALID_SIGNATURE"})
        return httpx.Response(200, json={"status": "PROCESSED"})

    transport = httpx.MockTransport(handle_request)
    client = httpx.Client(transport=transport)
    replayer = WebhookReplayer(endpoint_url="http://testserver/api/webhooks", client=client)

    payload = build_webhook_payload(event_id="WH-TEST-1")

    # 1. Unsigned should return 401
    res_unsigned = replayer.replay_unsigned(payload)
    assert res_unsigned["status_code"] == 401
    assert res_unsigned["body"]["error"] == "INVALID_SIGNATURE"

    # 2. Duplicate replay should send multiple requests
    res_dup = replayer.replay_duplicate(payload, count=2)
    assert len(res_dup) == 2
    assert res_dup[0]["status_code"] == 200
    assert res_dup[1]["status_code"] == 200
    assert len(calls) == 3

