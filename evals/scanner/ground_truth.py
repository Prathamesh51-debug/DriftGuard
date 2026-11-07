"""
Ground truth benchmark labels for evaluating the DriftGuard Static Code Scanner.
Planner Ref: Part 10 (Required Evals Table - Scanner Precision/Recall).
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class ExpectedFinding(BaseModel):
    file: str
    target_line: int
    tolerance: int = 5
    primary_risk: str
    bug_id: Optional[str] = None
    description: str


# 1. Ten Seeded Ground Truth Sites in Demo Shop
SEEDED_BENCHMARK: List[ExpectedFinding] = [
    ExpectedFinding(
        file="src/checkout.ts",
        target_line=163,
        primary_risk="MISSING_IDEMPOTENCY_KEY",
        bug_id="BUG-01",
        description="Capture retry without PayPal-Request-Id header",
    ),
    ExpectedFinding(
        file="src/checkout.ts",
        target_line=92,
        primary_risk="MISSING_IDEMPOTENCY_KEY",
        bug_id="BUG-02",
        description="Create order timeout retry without idempotency key",
    ),
    ExpectedFinding(
        file="src/checkout.ts",
        target_line=193,
        primary_risk="UNHANDLED_DECLINE",
        bug_id="BUG-03",
        description="422 INSTRUMENT_DECLINED treated as completed fulfillment",
    ),
    ExpectedFinding(
        file="src/checkout.ts",
        target_line=100,
        primary_risk="NON_DETERMINISTIC_INVOICE",
        bug_id="BUG-04",
        description="Math.random() non-deterministic invoice ID",
    ),
    ExpectedFinding(
        file="src/checkout.ts",
        target_line=44,
        primary_risk="FLOAT_ROUNDING",
        bug_id="BUG-05",
        description="Floating-point sales tax truncation",
    ),
    ExpectedFinding(
        file="src/webhooks.ts",
        target_line=28,
        primary_risk="UNVERIFIED_WEBHOOK",
        bug_id="BUG-08",
        description="Unverified webhook transmission signature",
    ),
    ExpectedFinding(
        file="src/webhooks.ts",
        target_line=39,
        primary_risk="DUPLICATE_WEBHOOK_PROCESSING",
        bug_id="BUG-09",
        description="Missing duplicate event deduplication set",
    ),
    ExpectedFinding(
        file="src/assistant.ts",
        target_line=30,
        primary_risk="UNGUARDED_AI_REFUND",
        bug_id="BUG-10",
        description="AI assistant prompt injection unauthorized refund bypass",
    ),
]

# 2. Five Real Repo Benchmark Snippets (Representative subset from study/repos.json)
REAL_REPOS_BENCHMARK = [
    {
        "repo_id": "repo-01",
        "name": "e-commerce-node-ts",
        "code": """
        async function capturePayment(orderId) {
          return await ordersController.captureOrder({ id: orderId });
        }
        """,
        "expected_vulnerable": True,
        "expected_risk": "MISSING_IDEMPOTENCY_KEY",
    },
    {
        "repo_id": "repo-02",
        "name": "react-paypal-marketplace",
        "code": """
        app.post('/api/orders/capture', async (req, res) => {
          const resp = await fetch('https://api.sandbox.paypal.com/v2/checkout/orders/' + req.body.id + '/capture', {
            method: 'POST'
          });
        });
        """,
        "expected_vulnerable": True,
        "expected_risk": "MISSING_IDEMPOTENCY_KEY",
    },
    {
        "repo_id": "repo-04",
        "name": "saas-subscription-service",
        "code": """
        async function captureWithKey(orderId) {
          const key = crypto.createHash('sha256').update(orderId).digest('hex');
          return await ordersController.captureOrder({ id: orderId, paypalRequestId: key });
        }
        """,
        "expected_vulnerable": False,
        "expected_risk": None,
    },
    {
        "repo_id": "repo-05",
        "name": "flutter-order-backend",
        "code": """
        for attempt in range(3):
          try:
            res = http.post('/v2/checkout/orders/capture')
          except Timeout:
            continue
        """,
        "expected_vulnerable": True,
        "expected_risk": "BLIND_RETRY_TIMEOUT",
    },
    {
        "repo_id": "repo-08",
        "name": "ticketing-platform-api",
        "code": """
        HttpHeaders headers = new HttpHeaders();
        headers.set("PayPal-Request-Id", transactionToken);
        HttpEntity entity = new HttpEntity<>(body, headers);
        restTemplate.postForEntity(captureUrl, entity, String.class);
        """,
        "expected_vulnerable": False,
        "expected_risk": None,
    },
]

