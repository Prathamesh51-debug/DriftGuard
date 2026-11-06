"""
DriftGuard Orchestrator: End-to-End Test Execution State Machine.
Coordinates: Target App -> Headless Buyer Driver -> Chaos Proxy -> Reconciler.
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
import requests

# Ensure repo root is in Python path for module resolution
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts import Evidence, FaultType, ObservedState, Result, Scenario, Verdict
from engine.reconciler import reconcile_order


def set_active_proxy_fault(fault: str, logs_dir: Optional[Path] = None):
    """Dynamically set the active fault for mitmproxy via the shared logs volume."""
    path = (logs_dir or (ROOT_DIR / "logs")) / "active_fault.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fault": fault.upper(), "timestamp": time.time()}), encoding="utf-8")
        print(f"[ORCHESTRATOR] 0. Armed proxy fault: {fault.upper()}")
    except Exception as e:
        print(f"[ORCHESTRATOR] Warning: could not write active_fault.json: {e}")


def _action_replay_event(scenario: Scenario, context: Dict[str, Any]) -> None:
    """Action handler: executes webhook replay attack strictly driven by scenario contract."""
    from ai.webhook_replayer import WebhookReplayer, build_webhook_payload

    shop_base = context["shop_base"]
    order_id = context.get("order_id", "ORDER-TEST-001")
    payload_cfg = scenario.inject.payload or {} if scenario.inject else {}

    replayer = WebhookReplayer(endpoint_url=f"{shop_base}/api/webhooks")
    event_id = payload_cfg.get("event_id")
    webhook_body = build_webhook_payload(
        event_id=event_id,
        order_id=order_id,
        amount=scenario.expect.amount or "38.97",
        currency=scenario.expect.currency or "USD",
    )
    count = payload_cfg.get("replay_count", 2)
    print(f"[ORCHESTRATOR] Executing action '{scenario.inject.action}' on {shop_base}/api/webhooks...")
    replay_res = replayer.replay_duplicate(webhook_body, count=count)
    print(f"[ORCHESTRATOR] Replayed webhook {webhook_body['id']} {count}x (HTTP {[r['status_code'] for r in replay_res]})")


# Post-capture active injection registry — keyed strictly by scenario.inject.action
POST_CAPTURE_ACTIONS = {
    "replay_event": _action_replay_event,
}


def run_scenario(
    scenario: Scenario,
    target_shop_url: str = "http://localhost:3001",
    proxy_url: str = "http://localhost:8080",
    max_retries: int = 1
) -> Result:
    """
    Executes an end-to-end chaos test run on a target shop:
    0. Dynamically arms chaos proxy with the scenario fault (no container restart required)
    1. Creates order on target shop (POST /api/orders)
    2. Approves order headlessly via Playwright (ai.buyer_driver)
    3. Triggers capture on target shop (POST /api/orders/:id/capture)
    4. Runs Reconciler to generate mathematically proven Result
    """
    shop_base = target_shop_url.rstrip("/")

    # 0. Dynamically arm chaos proxy
    fault_code = scenario.fault.value.split("_")[0].upper()
    set_active_proxy_fault(fault_code)

    # 1. Create order on target shop
    print(f"\n[ORCHESTRATOR] 1. Creating order on {shop_base}/api/orders...")
    order_amount = "38.97"
    if scenario.expect.amount:
        try:
            if float(scenario.expect.amount) > 0:
                order_amount = scenario.expect.amount
        except ValueError:
            pass

    order_body: Dict[str, Any] = {"amount": order_amount}
    if scenario.inject and scenario.inject.payload:
        order_body.update(scenario.inject.payload)
    if scenario.expect.currency:
        order_body.setdefault("currency", scenario.expect.currency)

    try:
        res = requests.post(
            f"{shop_base}/api/orders",
            json=order_body,
            timeout=15
        )
        if res.status_code not in (200, 201):
            return Result(
                scenario_id=scenario.scenario_id,
                verdict=Verdict.ERROR,
                rule="order_creation == 201",
                observed=ObservedState(captures=0, amount_captured="0.00"),
                evidence=Evidence(),
                money_impact="error: failed to create order on target app",
                error_message=f"Shop returned HTTP {res.status_code}: {res.text}"
            )
        order_data = res.json()
        order_id = order_data["orderId"]
        approve_url = order_data["approveUrl"]
        print(f"[ORCHESTRATOR] Order created: {order_id}")
    except Exception as e:
        return Result(
            scenario_id=scenario.scenario_id,
            verdict=Verdict.ERROR,
            rule="target_reachable",
            observed=ObservedState(captures=0, amount_captured="0.00"),
            evidence=Evidence(),
            money_impact="error: target shop unreachable",
            error_message=str(e)
        )

    # 2. Automated Headless Buyer Approval (Role C driver)
    print(f"[ORCHESTRATOR] 2. Approving order headlessly via Playwright...")
    try:
        from ai.buyer_driver import approve_order
        approval = approve_order(approve_url)
    except ImportError as e:
        return Result(
            scenario_id=scenario.scenario_id,
            verdict=Verdict.ERROR,
            rule="buyer_driver_available",
            observed=ObservedState(captures=0, amount_captured="0.00"),
            evidence=Evidence(paypal_order_ids=[order_id]),
            money_impact="error: Playwright buyer driver not installed",
            error_message=f"Install playwright via 'pip install playwright && playwright install chromium': {e}"
        )

    if not approval.approved:
        print(f"[ORCHESTRATOR] Approval failed: {approval.error}")
        return Result(
            scenario_id=scenario.scenario_id,
            verdict=Verdict.ERROR,
            rule="buyer_approval == True",
            observed=ObservedState(captures=0, amount_captured="0.00"),
            evidence=Evidence(paypal_order_ids=[order_id]),
            money_impact="error: buyer approval failed",
            error_message=approval.error or "Approval timed out"
        )
    print(f"[ORCHESTRATOR] Order approved in {approval.duration_s}s!")

    # 3. Trigger capture on target shop
    print(f"[ORCHESTRATOR] 3. Triggering capture on {shop_base}/api/orders/{order_id}/capture...")
    try:
        # Capture may return 502/504 because the demo shop catches the proxy drop
        cap_res = requests.post(f"{shop_base}/api/orders/{order_id}/capture", timeout=30)
        print(f"[ORCHESTRATOR] Target shop capture response: HTTP {cap_res.status_code}")
    except Exception as e:
        print(f"[ORCHESTRATOR] Capture request threw exception: {e}")

    # Brief delay to let proxy write its audit log
    time.sleep(1)

    # 4. Dispatch post-capture active injection action if specified by scenario contract
    if scenario.inject and scenario.inject.action in POST_CAPTURE_ACTIONS:
        action_fn = POST_CAPTURE_ACTIONS[scenario.inject.action]
        try:
            action_fn(scenario, {"shop_base": shop_base, "order_id": order_id})
        except Exception as e:
            print(f"[ORCHESTRATOR] Active injection action '{scenario.inject.action}' error: {e}")

    # 5. Run Reconciler to produce final ground truth Result
    print(f"[ORCHESTRATOR] 4. Reconciling ground truth from PayPal records...")
    result = reconcile_order(
        scenario=scenario,
        order_id=order_id,
        demo_shop_url=shop_base
    )
    print(f"[ORCHESTRATOR] Verdict: {result.verdict.value} | Impact: {result.money_impact}")
    return result


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="DriftGuard Automated Chaos Runner")
    parser.add_argument(
        "--fault",
        default=os.getenv("DRIFTGUARD_FAULT", "F1").upper(),
        help="Fault type to run (F1, F2, F3, F4, F5, F6). Defaults to env DRIFTGUARD_FAULT or F1",
    )
    args = parser.parse_args()

    fault_key = args.fault.lower().split("_")[0]  # e.g. "f1" or "f2"
    fixtures_dir = ROOT_DIR / "contracts" / "fixtures"
    scenario_path = fixtures_dir / f"{fault_key}_scenario.json"

    if not scenario_path.exists():
        print(f"Error: Fixture not found at {scenario_path}")
        sys.exit(1)

    scenario = Scenario.model_validate_json(scenario_path.read_text(encoding="utf-8"))

    print("=================================================================")
    print(f"DRIFTGUARD AUTOMATED CHAOS LOOP: FAULT {args.fault.upper()}")
    print("=================================================================")
    res = run_scenario(scenario)
    print("\n======================= FINAL RESULT =======================")
    print(res.model_dump_json(indent=2))
