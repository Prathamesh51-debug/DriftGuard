"""
Fixer eval: run the Fixer N times on a bug and report how often it produces a correct fix.

    python -m evals.fixer.run_eval --runs 10 --providers anthropic
    python -m evals.fixer.run_eval --runs 5 --providers gemini,groq --save

Measures the model alone: the curated-fix fallback is off and the reply cache is off, so every
run is a fresh sample. Paid providers go through the spend guard. Planner Ref: Part 8 (Fixer eval table).
"""

import argparse
import shutil
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List

from ai.fixer import apply_to_copy, find_bug, load_bugs, propose_fix
from ai.fixer.llm import LLMClient, LLMError
from ai.fixer.providers import SpendGuard, llm_from_env
from contracts import Result, Scenario
from evals.fixer.checks import CHECKS, check_patched

ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "targets" / "demo-shop"
FIXTURES = ROOT / "contracts" / "fixtures"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
FIXTURES_BY_FAULT = {"F1_LOST_CAPTURE_RESPONSE": ("f1_scenario.json", "f1_result_fail.json")}


def evaluate(bug_id: str, runs: int, llm_factory: Callable[[int], LLMClient], shop_dir: Path = SHOP) -> Dict:
    bug = next(b for b in load_bugs() if b.id == bug_id)
    if bug.fault not in FIXTURES_BY_FAULT:
        raise SystemExit(f"no scenario/result fixtures for {bug.fault} yet")
    scenario_file, result_file = FIXTURES_BY_FAULT[bug.fault]
    scenario = Scenario.model_validate_json((FIXTURES / scenario_file).read_text(encoding="utf-8"))
    result = Result.model_validate_json((FIXTURES / result_file).read_text(encoding="utf-8"))
    bug = find_bug(scenario, [bug])

    rows: List[Dict] = []
    scratch = Path(tempfile.mkdtemp(prefix="driftguard-eval-"))
    try:
        for i in range(1, runs + 1):
            llm = llm_factory(i)
            started = time.time()
            try:
                fix = propose_fix(result, scenario, bug, shop_dir, llm, known_fixes=[])
            except LLMError as exc:
                fix, error = None, str(exc)
            seconds = round(time.time() - started, 1)

            row = {"run": i, "seconds": seconds, "applies": False, "attempts": None, "correct": None,
                   "provider": getattr(llm, "last_provider", None), "problems": [], "error": None}
            if fix is not None:
                row.update(applies=fix.applies, attempts=fix.attempts, error=fix.error)
            else:
                row["error"] = error
            if fix is not None and fix.applies:
                patched = apply_to_copy(fix.diff, shop_dir, scratch / f"run{i}")
                if bug.id in CHECKS:
                    row["problems"] = check_patched(bug.id, (patched / bug.file).read_text(encoding="utf-8"))
                    row["correct"] = not row["problems"]
            rows.append(row)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    return {
        "bug": bug.id, "runs": runs, "rows": rows,
        "applies": sum(r["applies"] for r in rows),
        "first_try": sum(bool(r["applies"] and r["attempts"] == 1) for r in rows),
        "correct": sum(bool(r["correct"]) for r in rows),
        "checked": bug.id in CHECKS,
        "avg_seconds": round(sum(r["seconds"] for r in rows) / max(len(rows), 1), 1),
        "providers": dict(Counter(r["provider"] for r in rows if r["provider"])),
    }


def to_markdown(summary: Dict, providers: str) -> str:
    n = summary["runs"]
    correct = f"{summary['correct']}/{n}" if summary["checked"] else "no check yet"
    lines = [
        f"### Fixer eval: {summary['bug']} ({providers})",
        "",
        "| Runs | Diff applies | Applies on first try | Behaves correctly | Avg seconds |",
        "|---|---|---|---|---|",
        f"| {n} | {summary['applies']}/{n} | {summary['first_try']}/{n} | {correct} | {summary['avg_seconds']} |",
        "",
        "Answered by: " + (", ".join(f"{k} x{v}" for k, v in summary["providers"].items()) or "no model answered"),
    ]
    failed = [r for r in summary["rows"] if not r["applies"] or r["problems"]]
    if failed:
        lines += ["", "Failures:"]
        for r in failed:
            why = "; ".join(r["problems"]) or (r["error"] or "unknown")
            lines.append(f"- run {r['run']}: {why.splitlines()[0][:160]}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Fixer N times on a bug and report how often it is right.")
    parser.add_argument("--bug", default="BUG-01")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--providers", default=None, help='e.g. "anthropic" or "gemini,groq" (default: DRIFTGUARD_LLM)')
    parser.add_argument("--save", action="store_true", help="also write the table to evals/fixer/results/")
    args = parser.parse_args()

    summary = evaluate(args.bug, args.runs, lambda i: llm_from_env(args.providers, cache=False))
    label = args.providers or "default providers"
    table = to_markdown(summary, label)
    print(table)
    if args.providers and "anthropic" in args.providers:
        print(f"Anthropic spend so far: ${SpendGuard(1.5).spent_usd:.4f}")
    if args.save:
        RESULTS_DIR.mkdir(exist_ok=True)
        out = RESULTS_DIR / f"{args.bug}-{label.replace(',', '+')}.md"
        out.write_text(table, encoding="utf-8")
        print(f"saved {out}")


if __name__ == "__main__":
    main()
