"""
DriftGuard Background Worker: Asynchronous Job Consumer.
Planner Ref: Role Playbook A (A1 - Postgres SKIP LOCKED queue & worker crash resilience).

Pulls queued chaos test runs from PostgreSQL using SELECT ... FOR UPDATE SKIP LOCKED
and executes them via the Orchestrator state machine.
"""

import os
import sys
import time
import signal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts import Scenario, Result, Verdict, ObservedState, Evidence
from engine.orchestrator.db import db
from engine.orchestrator.runner import run_scenario

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    print(f"\n[WORKER] Caught shutdown signal ({signum}). Exiting gracefully...")
    _shutdown = True


def start_worker(poll_interval: float = 2.0):
    """
    Continuous worker loop polling for pending runs using concurrency-safe SKIP LOCKED.
    """
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    print("[WORKER] Initializing database backend...")
    db.init_db()
    backend = "PostgreSQL (SKIP LOCKED)" if db.use_postgres else "SQLite fallback"
    print(f"[WORKER] DriftGuard Worker started. Backend: {backend}. Polling every {poll_interval}s...")

    while not _shutdown:
        try:
            job = db.fetch_next_pending_run_skip_locked()
            if job:
                run_id = job["run_id"]
                scenario_raw = job["scenario"]
                print(f"\n[WORKER] Picked up pending run: {run_id}")
                try:
                    scenario = Scenario.model_validate(scenario_raw)
                    result = run_scenario(scenario)
                    db.update_run_result(run_id, "complete", result.model_dump())
                    print(f"[WORKER] Run {run_id} finished with verdict: {result.verdict.value}")
                except Exception as e:
                    print(f"[WORKER ERROR] Execution of {run_id} failed: {e}")
                    error_result = Result(
                        scenario_id=scenario_raw.get("scenario_id", "unknown"),
                        verdict=Verdict.ERROR,
                        rule="worker_execution",
                        observed=ObservedState(captures=0, amount_captured="0.00"),
                        evidence=Evidence(),
                        money_impact="error: worker failed during execution",
                        error_message=str(e),
                    )
                    db.update_run_result(run_id, "error", error_result.model_dump())
            else:
                time.sleep(poll_interval)
        except Exception as loop_err:
            print(f"[WORKER LOOP ERROR] {loop_err}")
            time.sleep(poll_interval)

    print("[WORKER] Worker shutdown complete.")


if __name__ == "__main__":
    start_worker()

