"""
PayPal Direct REST Client (Ground Truth Ledger Inspector).
Planner Ref: Role Playbook A (A3 - Reconciler).
Bypasses proxy and inspects api-m.sandbox.paypal.com directly.
"""

import os
from decimal import Decimal
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PAYPAL_API_BASE_URL", "https://api-m.sandbox.paypal.com")
CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")

class PayPalClient:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.client_id = client_id or CLIENT_ID
        self.client_secret = client_secret or CLIENT_SECRET
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self._token: Optional[str] = None
    
    def get_token(self) -> str:
        """Fetch or refresh OAuth2 client credentials token."""
        url = f"{self.base_url}/v1/oauth2/token"
        res = requests.post(
            url,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if res.status_code != 200:
            raise RuntimeError(f"PayPal authentication failed ({res.status_code}): {res.text}")
        self._token = res.json()["access_token"]
        return self._token
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Fetch raw order details from PayPal v2 Orders API."""
        if not self._token:
            self.get_token()
        url = f"{self.base_url}/v2/checkout/orders/{order_id}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 401:
            # Token might have expired, retry once
            self.get_token()
            headers["Authorization"] = f"Bearer {self._token}"
            res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            raise RuntimeError(f"Failed to fetch PayPal order {order_id} ({res.status_code}): {res.text}")
        return res.json()

    def parse_order_ledger(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract captures, total amount captured, and refunds from order JSON.
        """
        status = order_data.get("status", "UNKNOWN")
        units = order_data.get("purchase_units", [])
        
        captures: List[Dict[str, Any]] = []
        refunds: List[Dict[str, Any]] = []
        total_captured = Decimal("0.00")
        
        for unit in units:
            payments = unit.get("payments", {})
            for cap in payments.get("captures", []):
                captures.append(cap)
                val = cap.get("amount", {}).get("value", "0.00")
                if cap.get("status") in ("COMPLETED", "PARTIALLY_REFUNDED"):
                    total_captured += Decimal(val)
            for ref in payments.get("refunds", []):
                refunds.append(ref)
        return {
            "order_id": order_data.get("id"),
            "status": status,
            "captures": captures,
            "capture_ids": [c["id"] for c in captures if "id" in c],
            "refunds": refunds,
            "refund_ids": [r["id"] for r in refunds if "id" in r],
            "total_captured_amount": f"{total_captured:.2f}",
        }

    

