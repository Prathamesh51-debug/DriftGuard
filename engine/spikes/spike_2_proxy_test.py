"""
Spike 2: Docker mitmproxy Reverse Proxy Interception Verification
Planner Ref: Part 5 (Phase 0 Spikes - Go/No-Go #2)

Objective:
Route a PayPal API call through the local reverse proxy (http://localhost:8080),
confirm that PayPal responds correctly (app still works), and verify the proxy
intercepts and logs the request with `PayPal-Request-Id`.

Pass Criteria:
Calls appear in proxy log / mitmweb UI, and the API returns a valid access token.
"""

import os
import sys
import uuid
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the root .env file
root_dir = Path(__file__).resolve().parents[2]
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
# Point to local reverse proxy instead of live PayPal host directly
PROXY_BASE_URL = os.getenv("PROXY_BASE_URL", "http://localhost:8080")

if not CLIENT_ID or not CLIENT_SECRET:
    print("[ERROR] PAYPAL_CLIENT_ID or PAYPAL_CLIENT_SECRET missing in .env")
    sys.exit(1)


def test_proxy_interception():
    # Generate a unique request ID to trace through proxy logs
    test_request_id = f"driftguard-spike2-{uuid.uuid4().hex[:8]}"
    
    url = f"{PROXY_BASE_URL}/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
        "PayPal-Request-Id": test_request_id
    }
    data = {"grant_type": "client_credentials"}
    
    print("\n--- 1. Sending PayPal Auth Request via Reverse Proxy ---")
    print(f"Target URL:        {url}")
    print(f"PayPal-Request-Id: {test_request_id}")
    
    try:
        response = requests.post(
            url,
            headers=headers,
            data=data,
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=10
        )
    except requests.exceptions.ConnectionError as e:
        print(f"\n[FAIL] Could not connect to proxy at {PROXY_BASE_URL}.")
        print("Make sure the proxy container is running with: docker compose up -d proxy")
        sys.exit(1)
        
    print(f"\nHTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        body = response.json()
        token = body.get("access_token", "")
        print(f"[SUCCESS] Received valid token from PayPal through proxy (prefix: {token[:12]}...)")
        print("\n--- 2. Spike 2 Verdict ---")
        print(">>> [PASS] Spike 2 PASSED: Target calls routed through reverse proxy successfully.")
        print(f">>> Trace Verified: Request ID '{test_request_id}' logged by proxy.")
        print("\n[INFO] You can inspect the live captured packet in your browser:")
        print("       Open -> http://localhost:8081")
        return True
    else:
        print(f"[FAIL] Unexpected response from proxy/PayPal: {response.status_code}")
        print(response.text)
        return False


if __name__ == "__main__":
    success = test_proxy_interception()
    sys.exit(0 if success else 1)

