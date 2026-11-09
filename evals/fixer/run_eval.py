"""
Fixer source eval: run the Fixer N times and measure patch acceptance and source checks.

    python -m evals.fixer.run_eval --runs 10 --providers anthropic
    python -m evals.fixer.run_eval --runs 5 --providers gemini,groq --save
    python -m evals.fixer.run_eval --runs 10 --providers anthropic --no-sdk-notes --save   # ablation
    python -m evals.fixer.run_eval --runs 10 --providers anthropic --blind --save          # no hints in the source

Measures the model alone: the curated-fix fallback is off and the reply cache is off, so every
run is a fresh sample. Paid providers go through the spend guard. A source check is not a live
PayPal Sandbox rerun; keep live verdicts in a separate report. Planner Ref: Part 8.
"""

import argparse
import contextlib
import re
import shutil
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List

from ai.fixer import apply_to_copy, find_bug, load_bugs, propose_fix
from ai.fixer import fixer as fixer_module
from ai.fixer import prompt as fixer_prompt
from ai.fixer.llm import LLMClient, LLMError
from ai.fixer.providers import SpendGuard, llm_from_env
from contracts import Result, Scenario
from evals.fixer.checks import CHECKS, check_patched

ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "targets" / "demo-shop"
FIXTURES = ROOT / "contracts" / "fixtures"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
FIXTURES_BY_FAULT = {
    "F1_LOST_CAPTURE_RESPONSE": ("f1_scenario.json", "f1_result_fail.json"),
    "F2_SLOW_PAYPAL": ("f2_scenario.json", "f2_result_fail.json"),
    "F3_FORCED_DECLINE": ("f3_scenario.json", "f3_result_fail.json"),
    "F4_DUPLICATE_INVOICE": ("f4_scenario.json", "f4_result_fail.json"),
    "F6_WEBHOOK_REPLAY": ("f6_scenario.json", "f6_result_fail.json"),
}


HINT = re.compile(r"BUG-\d+|idempot|request-?id", re.IGNORECASE)


def blind_copy(shop_dir: Path, into: Path) -> Path:
    """Copy of the shop with every comment line that names the bug or its fix removed, so the model has
    to find the problem from the failing result and the code, not from the seeded-bug comments."""
    shutil.copytree(shop_dir, into, ignore=shutil.ignore_patterns("node_modules", ".git", "dist"))
    for path in (into / "src").rglob("*.ts"):
        lines = path.read_text(encoding="utf-8").splitlines()
        keep = [ln for ln in lines if not (ln.strip().startswith(("//", "*", "/*")) and HINT.search(ln))]
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")
    return into


@contextlib.contextmanager
def without_sdk_notes():
    """Ablation: take the APIMatic-derived SDK notes out of the prompt, and the rule that points at them."""
    notes, system = fixer_prompt.SDK_NOTES, fixer_module.SYSTEM_PROMPT
    fixer_prompt.SDK_NOTES = {}
    fixer_module.SYSTEM_PROMPT = system.replace(
        "Use only SDK options listed under SDK notes. Do not invent APIs.", "Do not invent APIs.")
    assert fixer_module.SYSTEM_PROMPT != system, "system prompt rule changed; update the ablation"
    try:
        yield
    finally:
        fixer_prompt.SDK_NOTES, fixer_module.SYSTEM_PROMPT = notes, system


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
        "| Runs | Diff applies | Applies on first try | Source check passes | Avg generation seconds |",
        "|---|---|---|---|---|",
        f"| {n} | {summary['applies']}/{n} | {summary['first_try']}/{n} | {correct} | {summary['avg_seconds']} |",
        "",
        "Source checks only. Live PayPal Sandbox re-runs are reported separately.",
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
    parser.add_argument("--no-sdk-notes", action="store_true", help="ablation: leave the APIMatic SDK notes out of the prompt")
    parser.add_argument("--blind", action="store_true", help="strip comments that name the bug or its fix from the source")
    parser.add_argument("--save", action="store_true", help="also write the table to evals/fixer/results/")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="driftguard-blind-"))
    try:
        shop = blind_copy(SHOP, workdir / "shop") if args.blind else SHOP
        with without_sdk_notes() if args.no_sdk_notes else contextlib.nullcontext():
            summary = evaluate(args.bug, args.runs, lambda i: llm_from_env(args.providers, cache=False), shop)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    label = ", ".join([args.providers or "default providers"] + (["no SDK notes"] if args.no_sdk_notes else [])
                      + (["blind source"] if args.blind else []))
    table = to_markdown(summary, label)
    print(table)
    if args.providers and "anthropic" in args.providers:
        print(f"Anthropic spend so far: ${SpendGuard(1.5).spent_usd:.4f}")
    if args.save:
        RESULTS_DIR.mkdir(exist_ok=True)
        out = RESULTS_DIR / f"{args.bug}-{label.replace(', ', '-').replace(' ', '-').replace(',', '+')}.md"
        out.write_text(table, encoding="utf-8")
        print(f"saved {out}")


if __name__ == "__main__":
    main()
