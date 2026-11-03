"""
DriftGuard CLI.

    python -m cli run                    start a chaos run, wait for PayPal's verdict, print the report
    python -m cli report [RUN_ID]        print a stored run (the newest if no id); --all lists every run

Exit code: 0 = PASS, 1 = FAIL (a real problem found), 2 = no verdict (error, timeout, engine unreachable).
The engine address comes from --api or ENGINE_BASE_URL (default http://localhost:8000).
Planner Ref: Part 8 (CLI skeleton Fri 6 Nov, driftguard run / report Sun 8 Nov).
"""

import argparse
import json
import os
import sys
import time
from typing import Callable, List, Optional

from contracts import FaultType

from .client import Engine, EngineError, Run
from .render import exit_code, fault_label, render_list, render_report

DEFAULT_API = "http://localhost:8000"
POLL_SECONDS = 1.0
DEFAULT_TIMEOUT_S = 180


def wait_for_result(engine: Engine, run: Run, timeout_s: float, say: Callable[[str], None],
                    sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> Run:
    """Poll until the run has a result. Raises EngineError on timeout."""
    deadline = clock() + timeout_s
    say(f"Run {run.run_id[4:]} started. Waiting for PayPal's records...")
    while run.result is None:
        if clock() >= deadline:
            raise EngineError(f"Gave up after {timeout_s:g}s: run {run.run_id} still has no result. The engine may be stuck.")
        sleep(POLL_SECONDS)
        run = engine.get(run.run_id)
    return run


def cmd_run(engine: Engine, args, out: Callable[[str], None], err: Callable[[str], None]) -> int:
    run = engine.launch(args.fault)
    if args.fault and run.scenario.fault.value != args.fault:
        raise EngineError(f"You asked for {args.fault}, but the engine ran {run.scenario.fault.value}. "
                          "It does not support that fault yet, so no verdict for it exists.")
    if not args.no_wait:
        run = wait_for_result(engine, run, args.timeout, err)
    out(json.dumps(run.model_dump(mode="json"), indent=2) if args.json else render_report(run))
    return exit_code(run)


def cmd_report(engine: Engine, args, out: Callable[[str], None], err: Callable[[str], None]) -> int:
    if args.all:
        runs = engine.list()
        out(json.dumps([r.model_dump(mode="json") for r in runs], indent=2) if args.json else render_list(runs))
        return 0
    if args.run_id:
        run = engine.get(args.run_id if args.run_id.startswith("run_") else f"run_{args.run_id}")
    else:
        runs = engine.list()
        if not runs:
            out(render_list([]))
            return 2
        run = max(runs, key=lambda r: r.created_at)
    out(json.dumps(run.model_dump(mode="json"), indent=2) if args.json else render_report(run))
    return exit_code(run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="driftguard", description="Chaos-test a PayPal integration and check PayPal's own records.")
    parser.add_argument("--api", default=os.getenv("ENGINE_BASE_URL", DEFAULT_API), help="engine address (default: ENGINE_BASE_URL or %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="start a chaos run and print the verdict")
    run.add_argument("--fault", choices=[f.value for f in FaultType], help="which fault to inject (default: the engine's default, F1)")
    run.add_argument("--no-wait", action="store_true", help="start the run and print its current state without waiting")
    run.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="seconds to wait for the verdict (default %(default)s)")
    run.add_argument("--json", action="store_true", help="print the run as JSON")
    run.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="print a stored run")
    rep.add_argument("run_id", nargs="?", help="run id, full or short (default: the newest run)")
    rep.add_argument("--all", action="store_true", help="list every run")
    rep.add_argument("--json", action="store_true", help="print as JSON")
    rep.set_defaults(func=cmd_report)
    return parser


def main(argv: Optional[List[str]] = None, engine: Optional[Engine] = None) -> int:
    args = build_parser().parse_args(argv)
    engine = engine or Engine(args.api)
    try:
        return args.func(engine, args, print, lambda m: print(m, file=sys.stderr))
    except EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
