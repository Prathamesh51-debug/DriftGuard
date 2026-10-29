"""
Spike 1: PayPal Mock Response Header Verification
Planner Ref: Part 5 (Phase 0 Spikes - Go/No-Go #1)

Objective:
Verify that PayPal Sandbox honors the `PayPal-Mock-Response` header
and returns an `INSTRUMENT_DECLINED` error upon capturing an order.

Pass Criteria:
Sandbox returns HTTP 422 with issue 'INSTRUMENT_DECLINED'.
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the root .env file
root_dir = Path(__file__).resolve().parents[2]
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[INFO] Loaded environment from {env_path}")
else:
    print(f"[WARN] No .env found at {env_path}, relying on system environment variables.")

CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
BASE_URL = os.getenv("PAYPAL_API_BASE_URL", "https://api-m.sandbox.paypal.com")

if not CLIENT_ID or not CLIENT_SECRET:
    print("[ERROR] PAYPAL_CLIENT_ID or PAYPAL_CLIENT_SECRET is missing. Check your .env file.")
    sys.exit(1)


def get_access_token() -> str:
    """Fetch OAuth2 Bearer token using Client ID & Secret."""
    url = f"{BASE_URL}/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
    }
    data = {"grant_type": "client_credentials"}
    
    print("\n--- 1. Authenticating with PayPal Sandbox ---")
    response = requests.post(url, headers=headers, data=data, auth=(CLIENT_ID, CLIENT_SECRET))
    
    if response.status_code != 200:
        print(f"[FAIL] Auth failed ({response.status_code}): {response.text}")
        sys.exit(1)
        
    token = response.json().get("access_token")
    print(f"[SUCCESS] Access token obtained (prefix: {token[:12]}...)")
    return token


def create_order(token: str) -> tuple[str, str]:
    """Create an order with intent=CAPTURE."""
    url = f"{BASE_URL}/v2/checkout/orders"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "spike-1-test-unit",
                "amount": {
                    "currency_code": "USD",
                    "value": "10.00"
                },
                "description": "DriftGuard Spike 1 Mock Capture Test"
            }
        ],
        "application_context": {
            "return_url": "https://example.com/return",
            "cancel_url": "https://example.com/cancel"
        }
    }
    
    print("\n--- 2. Creating Sandbox Order ---")
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code not in (200, 201):
        print(f"[FAIL] Order creation failed ({response.status_code}): {response.text}")
        sys.exit(1)
        
    data = response.json()
    order_id = data["id"]
    approve_url = next(link["href"] for link in data.get("links", []) if link.get("rel") == "approve")
    
    print(f"[SUCCESS] Order Created: {order_id}")
    print(f"[ACTION REQUIRED] Approve Order URL: {approve_url}")
    return order_id, approve_url


def test_mock_capture(token: str, order_id: str) -> bool:
    """Attempt capture with PayPal-Mock-Response header."""
    url = f"{BASE_URL}/v2/checkout/orders/{order_id}/capture"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        # PayPal Mock Response Header for Fault Simulation
        "PayPal-Mock-Response": json.dumps({"mock_application_codes": "INSTRUMENT_DECLINED"})
    }
    
    print("\n--- 3. Capturing Order with PayPal-Mock-Response ---")
    print(f"Header: PayPal-Mock-Response: {headers['PayPal-Mock-Response']}")
    response = requests.post(url, headers=headers)
    
    print(f"HTTP Status Code: {response.status_code}")
    print("Response Body:")
    try:
        body = response.json()
        print(json.dumps(body, indent=2))
    except Exception:
        print(response.text)
        body = {}
        
    print("\n--- 4. Spike 1 Verdict ---")
    # Check if INSTRUMENT_DECLINED was triggered
    issues = [
        issue.get("issue")
        for issue in body.get("details", [])
        if isinstance(issue, dict)
    ]
    
    if response.status_code == 422 and "INSTRUMENT_DECLINED" in issues:
        print(">>> [PASS] Spike 1 PASSED: Sandbox honored PayPal-Mock-Response with INSTRUMENT_DECLINED.")
        return True
    elif "INSTRUMENT_DECLINED" in str(body):
        print(">>> [PASS] Spike 1 PASSED: Mock application code INSTRUMENT_DECLINED observed in response.")
        return True
    else:
        print(f">>> [RESULT] Response did not trigger mock code directly (Status: {response.status_code}).")
        print("    If order was NOT approved, PayPal may return ORDER_NOT_APPROVED first.")
        return False


if __name__ == "__main__":
    access_token = get_access_token()
    order_id, approve_url = create_order(access_token)
    
    print("\n-------------------------------------------------------------")
    print("Please open the Approve URL in your browser, log in with your")
    print("sandbox Personal buyer account, and click 'Complete Purchase'.")
    print("-------------------------------------------------------------")
    input("Press ENTER once you have approved the payment in browser (or to test immediately)... ")
    
    success = test_mock_capture(access_token, order_id)
    sys.exit(0 if success else 1)

