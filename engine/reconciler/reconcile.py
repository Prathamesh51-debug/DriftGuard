"""
Deterministic Reconciler: Compares PayPal ground truth against local merchant state.
Planner Ref: Role Playbook A (A3 - Reconciler).
Rule 1: AI proposes, code decides.
Rule 2: Every verdict traces to PayPal IDs.
"""

import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts import Evidence, ObservedState, Result, Scenario, Verdict
from .client import PayPalClient

DEFAULT_LOG_PATH = ROOT_DIR / "logs" / "proxy_traffic.jsonl"


def harvest_proxy_log_refs(order_id: str, log_path: Optional[Path] = None) -> List[str]:
    """Extract PayPal-Request-Id headers and log references matching the order ID."""
    path = log_path or DEFAULT_LOG_PATH
    refs: List[str] = []
    if not path.exists():
        return refs

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if order_id in entry.get("path", ""):
                    req_id = entry.get("paypal_request_id")
                    if req_id and req_id != "NOT_SET" and req_id not in refs:
                        refs.append(req_id)
                    elif entry.get("request_body_hash"):
                        h_ref = f"hash_{entry['request_body_hash'][:12]}"
                        if h_ref not in refs:
                            refs.append(h_ref)
    except Exception:
        pass
    return refs


def fetch_app_state(demo_shop_url: str) -> Optional[Dict[str, Any]]:
    """Query target app's internal state endpoint: GET /_driftguard/state."""
    url = f"{demo_shop_url.rstrip('/')}/_driftguard/state"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def reconcile_order(
    scenario: Scenario,
    order_id: str,
    demo_shop_url: str = "http://localhost:3001",
    client: Optional[PayPalClient] = None,
    log_path: Optional[Path] = None,
) -> Result:
    """
    Reconciles an executed order against PayPal Ground Truth and target app state.
    Produces a mathematically sound, fully validated contracts.Result.
    """
    paypal = client or PayPalClient()
    
    # 1. Fetch live PayPal ledger records
    raw_order = paypal.get_order(order_id)
    ledger = paypal.parse_order_ledger(raw_order)

    # 2. Fetch demo shop internal state
    app_state = fetch_app_state(demo_shop_url)
    app_captures = None
    if app_state:
        # Find this specific order in the demo shop orders list
        for order in app_state.get("orders", []):
            if order.get("orderId") == order_id:
                app_captures = order.get("captureCount")
                break
        if app_captures is None:
            # Fall back to aggregate if order isn't isolated
            app_captures = app_state.get("totalCapturesRecorded", 0)

    # 3. Harvest proxy log references
    proxy_refs = harvest_proxy_log_refs(order_id, log_path)

    # 4. Construct ObservedState
    num_captures = len(ledger["captures"])
    observed = ObservedState(
        captures=num_captures,
        amount_captured=ledger["total_captured_amount"],
        orders_created=1,
        refunds_issued=len(ledger["refunds"]),
        app_recorded_captures=app_captures,
    )

    # 5. Construct Evidence
    evidence = Evidence(
        paypal_order_ids=[order_id],
        paypal_capture_ids=ledger["capture_ids"],
        paypal_refund_ids=ledger["refund_ids"],
        proxy_log_refs=proxy_refs,
        webhook_event_ids=[],
    )

    # 6. Deterministic Verdict Computation (Code decides!)
    rule = "app_recorded_captures == captures"
    expected_captures = scenario.expect.captures_per_purchase

    # Check state drift: does app state match PayPal reality?
    if app_captures is not None and app_captures == num_captures and num_captures == expected_captures:
        verdict = Verdict.PASS
        money_impact = f"clean: exactly one capture (+{observed.amount_captured} USD)"
    else:
        verdict = Verdict.FAIL
        if num_captures > 0 and (app_captures is None or app_captures == 0):
            money_impact = (
                f"buyer charged, but app recorded 0 captures: "
                f"{observed.amount_captured} USD paid without fulfillment"
            )
        elif num_captures > expected_captures:
            money_impact = (
                f"buyer double-charged: {num_captures} captures totaling "
                f"{observed.amount_captured} USD"
            )
        else:
            money_impact = (
                f"state drift detected: expected {expected_captures} captures, "
                f"got {num_captures} in PayPal vs {app_captures} in app"
            )

    return Result(
        scenario_id=scenario.scenario_id,
        verdict=verdict,
        rule=rule,
        observed=observed,
        evidence=evidence,
        money_impact=money_impact,
        error_message=None,
    )
