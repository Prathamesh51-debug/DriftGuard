"""Tests for Prompt Injection Library and Evaluator."""

import httpx
import pytest

from ai.injection import (
    AttackCategory,
    INJECTION_PAYLOADS,
    InjectionAttack,
    InjectionEvaluator,
)


def test_payload_library_completeness():
    assert len(INJECTION_PAYLOADS) == 25
    ids = [p.id for p in INJECTION_PAYLOADS]
    assert len(set(ids)) == 25

    categories = {p.category for p in INJECTION_PAYLOADS}
    assert len(categories) == 5
    for cat in AttackCategory:
        count = sum(1 for p in INJECTION_PAYLOADS if p.category == cat)
        assert count == 5, f"Expected 5 payloads for category {cat}, found {count}"


def test_evaluator_against_vulnerable_endpoint():
    # Simulates vulnerable assistant (BUG-10: returns 200 with refundTriggered=True)
    def mock_vulnerable(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "reply": "Refund processed.",
            "refundTriggered": True,
            "refundAmount": "500.00",
        })

    client = httpx.Client(transport=httpx.MockTransport(mock_vulnerable))
    evaluator = InjectionEvaluator(endpoint_url="http://testserver/api/chat", client=client)

    summary = evaluator.evaluate_all(INJECTION_PAYLOADS[:5])
    assert summary.total_attacks == 5
    assert summary.breaches == 5
    assert summary.breach_rate == 1.0


def test_evaluator_against_guarded_endpoint():
    # Simulates patched assistant (BUG-10 fixed: returns 403 with refundTriggered=False)
    def mock_guarded(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={
            "reply": "Refund exceeds policy limit.",
            "refundTriggered": False,
        })

    client = httpx.Client(transport=httpx.MockTransport(mock_guarded))
    evaluator = InjectionEvaluator(endpoint_url="http://testserver/api/chat", client=client)

    summary = evaluator.evaluate_all(INJECTION_PAYLOADS[:5])
    assert summary.total_attacks == 5
    assert summary.breaches == 0
    assert summary.breach_rate == 0.0

