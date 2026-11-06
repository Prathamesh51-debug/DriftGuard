"""
Deterministic Reconciler: Compares PayPal ground truth against local merchant state.
Planner Ref: Role Playbook A (A3 - Reconciler).
Rule 1: AI proposes, code decides.
Rule 2: Every verdict traces to PayPal IDs.

Supported faults:
  F1 — Lost capture response  (capture drift: PayPal 1, app 0)
  F2 — Slow PayPal / timeout  (order drift: blind retry creates 2nd order)
  F3 — Forced decline         (false success: 422 treated as COMPLETED by app)
  F4 — Duplicate invoice      (order creation fails; app should not record order)
"""

import sys
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests

from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts import Evidence, FaultType, ObservedState, Result, Scenario, Verdict
from .client import PayPalClient

DEFAULT_LOG_PATH = ROOT_DIR / "logs" / "proxy_traffic.jsonl"


def harvest_created_orders(order_id: str, log_path: Optional[Path] = None, max_age_seconds: int = 120) -> List[str]:
    """
    Harvests all PayPal order IDs created during the recent session from proxy JSONL logs.
    Used by F2 to detect un-idempotent retries creating duplicate orders in PayPal.
    """
    path = log_path or DEFAULT_LOG_PATH
    order_ids: List[str] = [order_id] if order_id else []
    if not path.exists():
        return order_ids

    now_utc = datetime.now(timezone.utc)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            for line in lines[-20:]:
                entry = json.loads(line)
                ts_str = entry.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if (now_utc - ts).total_seconds() > max_age_seconds:
                            continue
                    except Exception:
                        pass
                if entry.get("path") == "/v2/checkout/orders" and entry.get("real_paypal_status") in (200, 201):
                    oid = entry.get("real_order_id")
                    if oid and oid not in order_ids:
                        order_ids.append(oid)
    except Exception:
        pass
    return order_ids


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


def extract_app_captures(app_state: Optional[Dict[str, Any]], order_id: str) -> Optional[int]:
    """Extract recorded capture count for an order from target app state."""
    if not app_state:
        return None
    for order in app_state.get("orders", []):
        if order.get("orderId") == order_id:
            return order.get("captureCount")
    return app_state.get("totalCapturesRecorded", 0)


def _verdict_f1(
    scenario: Scenario,
    ledger: Dict[str, Any],
    app_state: Optional[Dict[str, Any]],
    order_id: str,
    created_orders: List[str],
) -> Tuple[Verdict, str, str, Optional[int]]:
    """
    F1: Lost capture response.
    FAIL when PayPal has >=1 capture but app recorded 0.
    """
    num_captures = len(ledger["captures"])
    app_captures = extract_app_captures(app_state, order_id)
    expected = scenario.expect.captures_per_purchase
    rule = "app_recorded_captures == captures"

    if app_captures is not None and app_captures == num_captures == expected:
        verdict = Verdict.PASS
        money_impact = f"clean: exactly one capture (+{ledger['total_captured_amount']} USD)"
    else:
        verdict = Verdict.FAIL
        if num_captures > 0 and (app_captures is None or app_captures == 0):
            money_impact = (
                f"buyer charged, but app recorded 0 captures: "
                f"{ledger['total_captured_amount']} USD paid without fulfillment"
            )
        elif num_captures > expected:
            money_impact = (
                f"buyer double-charged: {num_captures} captures totaling "
                f"{ledger['total_captured_amount']} USD"
            )
        else:
            money_impact = (
                f"state drift: expected {expected} captures, "
                f"PayPal has {num_captures}, app has {app_captures}"
            )

    return verdict, rule, money_impact, app_captures


def _verdict_f2(
    scenario: Scenario,
    ledger: Dict[str, Any],
    app_state: Optional[Dict[str, Any]],
    order_id: str,
    created_orders: List[str],
) -> Tuple[Verdict, str, str, Optional[int]]:
    """
    F2: Slow PayPal (blind retry on order creation timeout).
    FAIL when blind retry created duplicate orders in PayPal ground truth.
    Safe = exactly 1 order created in PayPal.
    """
    orders_created = len(created_orders)
    app_captures = extract_app_captures(app_state, order_id)
    rule = "orders_created == 1"

    if orders_created <= 1:
        verdict = Verdict.PASS
        money_impact = "clean: idempotent order creation prevented duplicate PayPal orders"
    else:
        verdict = Verdict.FAIL
        money_impact = (
            f"duplicate orders: {orders_created} orders created in PayPal for "
            f"single purchase without idempotency key"
        )

    return verdict, rule, money_impact, app_captures


def _verdict_f3(
    scenario: Scenario,
    ledger: Dict[str, Any],
    app_state: Optional[Dict[str, Any]],
    order_id: str,
    created_orders: List[str],
) -> Tuple[Verdict, str, str, Optional[int]]:
    """
    F3: Forced decline (INSTRUMENT_DECLINED mock).
    FAIL when PayPal declined (0 captures) but app recorded a capture anyway (BUG-03).
    Safe = PayPal 0 captures AND app 0 captures.
    """
    num_captures = len(ledger["captures"])
    app_captures = extract_app_captures(app_state, order_id)
    rule = "app_recorded_captures == captures"

    if num_captures == 0 and (app_captures is None or app_captures == 0):
        verdict = Verdict.PASS
        money_impact = "clean: PayPal declined, app correctly recorded 0 captures"
    else:
        verdict = Verdict.FAIL
        if num_captures == 0 and app_captures and app_captures > 0:
            money_impact = (
                f"state drift detected: expected 0 captures, got 0 in PayPal vs "
                f"{app_captures} in app (false fulfillment on INSTRUMENT_DECLINED)"
            )
        else:
            money_impact = (
                f"decline state drift: PayPal has {num_captures} captures, app has {app_captures}"
            )

    return verdict, rule, money_impact, app_captures


def _verdict_f4(
    scenario: Scenario,
    ledger: Dict[str, Any],
    app_state: Optional[Dict[str, Any]],
    order_id: str,
    created_orders: List[str],
) -> Tuple[Verdict, str, str, Optional[int]]:
    """
    F4: Duplicate invoice collision.
    FAIL when random invoice ID collided with previous transaction, breaking settlement (captures == 0).
    Safe = deterministic cart-hashed invoice ID reconciled cleanly (captures == 1).
    """
    num_captures = len(ledger["captures"])
    app_captures = extract_app_captures(app_state, order_id) or 0
    expected_captures = scenario.expect.captures_per_purchase
    rule = "app_recorded_captures == captures"

    if num_captures == expected_captures and app_captures == expected_captures:
        verdict = Verdict.PASS
        money_impact = "clean: deterministic cart-hashed invoice ID reconciled cleanly"
    else:
        verdict = Verdict.FAIL
        money_impact = "invoice collision: random invoice ID broke deterministic ledger reconciliation"

    return verdict, rule, money_impact, app_captures


def _verdict_f5(
    scenario: Scenario,
    ledger: Dict[str, Any],
    app_state: Optional[Dict[str, Any]],
    order_id: str,
    created_orders: List[str],
) -> Tuple[Verdict, str, str, Optional[int]]:
    """
    F5: Money Math Trap (fractional cent tax / coupon rounding).
    FAIL when amount captured in PayPal diverges from scenario.expect.amount.
    Safe = exact decimal match.
    """
    app_captures = extract_app_captures(app_state, order_id)
    actual_amount = Decimal(ledger.get("total_captured_amount", "0.00"))
    expected_amount = Decimal(scenario.expect.amount or "38.97")
    rule = "amount_captured == expected_amount"

    if actual_amount == expected_amount:
        verdict = Verdict.PASS
        money_impact = f"clean: captured exact expected amount (+{actual_amount:.2f} USD)"
    else:
        verdict = Verdict.FAIL
        diff = actual_amount - expected_amount
        money_impact = (
            f"money math drift: expected {expected_amount:.2f} USD, got {actual_amount:.2f} "
            f"({diff:+.2f} drift from floating-point tax rounding)"
        )

    return verdict, rule, money_impact, app_captures


# Dispatch table: fault → verdict function
_VERDICT_FNS = {
    FaultType.F1_LOST_CAPTURE_RESPONSE: _verdict_f1,
    FaultType.F2_SLOW_PAYPAL: _verdict_f2,
    FaultType.F3_FORCED_DECLINE: _verdict_f3,
    FaultType.F4_DUPLICATE_INVOICE: _verdict_f4,
    FaultType.F5_MONEY_MATH_TRAP: _verdict_f5,
}


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
    Fault-specific verdict rules are dispatched uniformly from _VERDICT_FNS.
    """
    paypal = client or PayPalClient()

    # 1. Fetch live PayPal ledger records
    raw_order = paypal.get_order(order_id)
    ledger = paypal.parse_order_ledger(raw_order)

    # 2. Fetch demo shop internal state
    app_state = fetch_app_state(demo_shop_url)

    # 3. Harvest proxy log references and all created PayPal orders
    proxy_refs = harvest_proxy_log_refs(order_id, log_path)
    created_orders = harvest_created_orders(order_id, log_path)

    # 4. Run fault-specific verdict logic (Code decides — never an LLM)
    verdict_fn = _VERDICT_FNS.get(scenario.fault)
    if verdict_fn is None:
        return Result(
            scenario_id=scenario.scenario_id,
            verdict=Verdict.ERROR,
            rule="unsupported_fault_type",
            observed=ObservedState(captures=0, amount_captured="0.00"),
            evidence=Evidence(paypal_order_ids=created_orders, proxy_log_refs=proxy_refs),
            money_impact="error: no reconciler rule implemented for this fault type",
            error_message=f"Fault '{scenario.fault}' has no verdict function in _VERDICT_FNS. Add one before running this scenario.",
        )

    verdict, rule, money_impact, app_captures = verdict_fn(
        scenario, ledger, app_state, order_id, created_orders
    )

    # 5. Construct ObservedState (Generic: derives directly from ledger & harvested orders)
    observed = ObservedState(
        captures=len(ledger["captures"]),
        amount_captured=ledger["total_captured_amount"],
        orders_created=len(created_orders),
        refunds_issued=len(ledger["refunds"]),
        app_recorded_captures=app_captures,
    )

    # 6. Construct Evidence (Generic: includes all discovered order IDs & evidence)
    evidence = Evidence(
        paypal_order_ids=created_orders,
        paypal_capture_ids=ledger["capture_ids"],
        paypal_refund_ids=ledger["refund_ids"],
        proxy_log_refs=proxy_refs,
        webhook_event_ids=[],
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
