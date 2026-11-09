"""Evaluate grounded explanations on stored live failures, with fresh model replies."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from ai.common.providers import SpendGuard, llm_from_env
from ai.explainer import explain, verify_text
from contracts import Result, Scenario


def evaluate(base_url: str, run_ids: list[str]) -> dict:
    guard = SpendGuard(1.5)
    before_spend = guard.spent_usd
    rows = []
    for run_id in run_ids:
        response = requests.get(f"{base_url}/runs/{run_id}", timeout=10)
        response.raise_for_status()
        run = response.json()
        scenario = Scenario.model_validate(run["scenario"])
        result = Result.model_validate(run["result"])
        if result.verdict.value != "FAIL":
            raise ValueError(f"{run_id} must be a completed failing run")
        llm = llm_from_env("anthropic", cache=False)
        started = time.monotonic()
        output = explain(result, scenario, llm)
        seconds = round(time.monotonic() - started, 1)
        problems = verify_text([output.headline, output.what_happened, output.impact], result, scenario)
        rows.append({"run_id": run_id, "fault": scenario.fault.value,
                     "source": output.source, "provider": output.provider,
                     "attempts": output.attempts, "rejected": output.rejected,
                     "seconds": seconds, "grounding_problems": problems,
                     "headline": output.headline,
                     "what_happened": output.what_happened,
                     "impact": output.impact})
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "fresh Anthropic replies on stored live FAIL results, reply cache off, strict code grounding",
        "runs": len(rows),
        "first_pass_without_regeneration": sum(r["source"] == "llm" and r["attempts"] == 1 for r in rows),
        "accepted_after_regeneration": sum(r["source"] == "llm" and r["attempts"] > 1 for r in rows),
        "template_fallbacks": sum(r["source"] == "template" for r in rows),
        "grounded_final_outputs": sum(not r["grounding_problems"] for r in rows),
        "avg_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 1),
        "spend_guard_usd_before": round(before_spend, 6),
        "spend_guard_usd_after": round(guard.spent_usd, 6),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_ids", nargs="+")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    data = evaluate(args.api.rstrip("/"), args.run_ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"first pass: {data['first_pass_without_regeneration']}/{data['runs']}")
    print(f"grounded final outputs: {data['grounded_final_outputs']}/{data['runs']}")
    print(f"fallbacks: {data['template_fallbacks']}; avg seconds: {data['avg_seconds']}")
    print(f"spend guard: ${data['spend_guard_usd_before']:.4f} -> ${data['spend_guard_usd_after']:.4f}")


if __name__ == "__main__":
    main()
