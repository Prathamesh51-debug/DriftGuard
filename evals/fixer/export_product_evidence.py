"""Export and validate stored red-to-green pairs from the running engine API."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


def export(base_url: str, pairs: list[str]) -> dict:
    rows = []
    for value in pairs:
        fault, parent_id, child_id = value.split(":", 2)
        parent = requests.get(f"{base_url}/runs/{parent_id}", timeout=10).json()
        child = requests.get(f"{base_url}/runs/{child_id}", timeout=10).json()
        assert parent["scenario"]["fault"].startswith(fault), value
        assert child["rerun_of"] == parent_id, value
        assert parent["result"]["verdict"] == "FAIL", value
        assert child["result"]["verdict"] == "PASS", value
        assert child["fix"]["proposal"]["applies"], value
        diff = child["fix"]["proposal"]["diff"]
        assert hashlib.sha256(diff.encode("utf-8")).hexdigest() == child["fix"]["patch_sha256"], value
        before_orders = parent["result"]["evidence"]["paypal_order_ids"]
        after_orders = child["result"]["evidence"]["paypal_order_ids"]
        assert before_orders and after_orders and set(before_orders).isdisjoint(after_orders), value
        rows.append({
            "fault": fault, "parent_run_id": parent_id, "child_run_id": child_id,
            "before": {"verdict": "FAIL", "observed": parent["result"]["observed"],
                       "paypal_order_ids": before_orders},
            "after": {"verdict": "PASS", "observed": child["result"]["observed"],
                      "paypal_order_ids": after_orders},
            "patch": {"bug_id": child["fix"]["proposal"]["bug_id"],
                      "source": child["fix"]["proposal"]["source"],
                      "sha256": child["fix"]["patch_sha256"]},
        })
    return {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "method": "stored engine API runs; separate PayPal Sandbox orders; proxy fault active",
            "passing_verified_reruns": len(rows), "attempted_verified_reruns": len(pairs),
            "runs": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs", nargs="+", help="FAULT:parent_run_id:child_run_id")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    data = export(args.api.rstrip("/"), args.pairs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"validated {data['passing_verified_reruns']}/{data['attempted_verified_reruns']} stored pairs")


if __name__ == "__main__":
    main()
