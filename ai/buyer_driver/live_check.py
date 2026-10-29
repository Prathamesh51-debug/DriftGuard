"""
Live check: create a sandbox order, approve it with the buyer driver, capture it.
Run from the repo root:  python -m ai.buyer_driver.live_check [runs]
"""

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from .driver import DEFAULT_RETURN_URL, approve_order

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BASE = os.getenv("PAYPAL_API_BASE_URL", "https://api-m.sandbox.paypal.com")
AUTH = (os.getenv("PAYPAL_CLIENT_ID", ""), os.getenv("PAYPAL_CLIENT_SECRET", ""))


def get_token() -> str:
    resp = requests.post(f"{BASE}/v1/oauth2/token", auth=AUTH, data={"grant_type": "client_credentials"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_order(token: str) -> tuple[str, str]:
    resp = requests.post(
        f"{BASE}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}", "PayPal-Request-Id": f"live-check-{time.time_ns()}"},
        json={
            "intent": "CAPTURE",
            "purchase_units": [{"amount": {"currency_code": "USD", "value": "10.00"}}],
            "payment_source": {"paypal": {"experience_context": {
                "return_url": DEFAULT_RETURN_URL,
                "cancel_url": "http://localhost:3000/cancel",
                "user_action": "PAY_NOW",
            }}},
        },
    )
    resp.raise_for_status()
    body = resp.json()
    link = next(l["href"] for l in body["links"] if l["rel"] in ("payer-action", "approve"))
    return body["id"], link


def main(runs: int) -> int:
    passed = 0
    for i in range(1, runs + 1):
        token = get_token()
        order_id, link = create_order(token)
        result = approve_order(link, screenshot_dir="ai/buyer_driver/shots")
        ok = result.approved and result.order_id == order_id
        if ok:
            cap = requests.post(
                f"{BASE}/v2/checkout/orders/{order_id}/capture",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                         "PayPal-Request-Id": f"live-check-cap-{order_id}"},
            )
            ok = cap.status_code == 201 and cap.json().get("status") == "COMPLETED"
        passed += ok
        print(f"run {i}: {'PASS' if ok else 'FAIL'} order={order_id} {result.duration_s}s {result.error or ''}")
    print(f"RESULT {passed}/{runs}")
    return 0 if passed == runs else 1


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
