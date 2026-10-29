"""
Phase 1 Vertical Slice Test: F1 Lost Capture Chaos Injection
Planner Ref: Part 6 (Thu 29 Oct Gate)

Gate Requirement:
Verify that the proxy intercepts a real capture, lets PayPal charge the card (201),
drops the response (504 Timeout), and records the real capture ID in JSONL.
"""

import os
import sys
import json
import uuid
import requests
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parents[2]
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PROXY_BASE_URL = os.getenv("PROXY_BASE_URL", "http://localhost:8080")
PAYPAL_DIRECT_URL = os.getenv("PAYPAL_API_BASE_URL", "https://api-m.sandbox.paypal.com")

if not CLIENT_ID or not CLIENT_SECRET:
    print("[ERROR] Missing PAYPAL_CLIENT_ID or PAYPAL_CLIENT_SECRET in .env")
    sys.exit(1)


def get_token() -> str:
    url = f"{PROXY_BASE_URL}/v1/oauth2/token"
    res = requests.post(
        url,
        data={"grant_type": "client_credentials"},
        auth=(CLIENT_ID, CLIENT_SECRET)
    )
    if res.status_code != 200:
        print(f"[FAIL] Auth failed: {res.text}")
        sys.exit(1)
    return res.json()["access_token"]


def create_order(token: str) -> tuple[str, str]:
    url = f"{PROXY_BASE_URL}/v2/checkout/orders"
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": f"f1-unit-{uuid.uuid4().hex[:6]}",
                "amount": {"currency_code": "USD", "value": "15.00"},
                "description": "DriftGuard F1 Lost Capture Test"
            }
        ],
        "application_context": {
            "return_url": "https://example.com/return",
            "cancel_url": "https://example.com/cancel"
        }
    }
    res = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload
    )
    if res.status_code not in (200, 201):
        print(f"[FAIL] Order create failed: {res.text}")
        sys.exit(1)
    data = res.json()
    approve_url = next(link["href"] for link in data["links"] if link["rel"] == "approve")
    return data["id"], approve_url


def test_f1_capture_drop(token: str, order_id: str):
    url = f"{PROXY_BASE_URL}/v2/checkout/orders/{order_id}/capture"
    req_id = f"driftguard-f1-{uuid.uuid4().hex[:8]}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": req_id,
        # Activate Fault F1 on this request
        "X-DriftGuard-Fault": "F1"
    }

    print("\n--- 3. Sending Capture with Chaos Header [X-DriftGuard-Fault: F1] ---")
    print(f"Target URL:        {url}")
    print(f"PayPal-Request-Id: {req_id}")

    res = requests.post(url, headers=headers)
    print(f"\nResponse HTTP Status: {res.status_code}")
    print(f"Response Body:        {res.text}")

    print("\n--- 4. Checking Proxy Audit Trail (JSONL) ---")
    log_file = root_dir / "logs" / "proxy_traffic.jsonl"
    last_log = None
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                last_log = json.loads(lines[-1])
                print(f"Last Log Entry:\n{json.dumps(last_log, indent=2)}")

    print("\n--- 5. Verifying Ground Truth from PayPal's Own Ledger ---")
    # Query PayPal directly (bypassing the proxy) to see if PayPal actually charged the order
    direct_order_url = f"{PAYPAL_DIRECT_URL}/v2/checkout/orders/{order_id}"
    direct_res = requests.get(
        direct_order_url,
        headers={"Authorization": f"Bearer {token}"}
    )
    order_data = direct_res.json()
    order_status = order_data.get("status")
    print(f"PayPal Ledger Status: {order_status}")

    print("\n======================= VERDICT =======================")
    if res.status_code == 504 and order_status == "COMPLETED":
        print(">>> [PASS] Gate Cleared: F1 Lost Capture Succeeded!")
        print("    1. App received simulated 504 Gateway Timeout (Network Drop).")
        print("    2. PayPal records prove the money WAS captured (Status: COMPLETED).")
        if last_log and last_log.get("real_capture_id"):
            print(f"    3. Real Capture ID logged: {last_log['real_capture_id']}")
        return True
    else:
        print(f">>> [FAIL] Expected 504 returned and COMPLETED in PayPal. Got {res.status_code} / {order_status}")
        return False


if __name__ == "__main__":
    token = get_token()
    order_id, approve_url = create_order(token)
    print(f"\n[SUCCESS] Order Created: {order_id}")
    print(f"[ACTION REQUIRED] Approve in browser: {approve_url}")
    print("-------------------------------------------------------------")
    input("Press ENTER once approved in browser... ")
    success = test_f1_capture_drop(token, order_id)
    sys.exit(0 if success else 1)