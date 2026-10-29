"""
Mock runner: a fixture-backed stand-in for the engine API so the dashboard,
Explainer and Fixer never wait on the real proxy and reconciler.

Planner Ref: Part 2 (Mock runner, Role C). Replaced by the real API on 31 Oct.

Mirrors the endpoints the engine will expose (/runs, /runs/{id}, rerun) and
serves the contracts fixtures, validated through contracts.Result/Scenario.
The run envelope (run_id, status, created_at) is mock-only: contracts has no
run model yet.

Run from the repo root:  uvicorn mock_runner.app:app --port 8000
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contracts import Result, Scenario

FIXTURES = Path(__file__).resolve().parents[1] / "contracts" / "fixtures"
RUNNING_SECONDS = 1.5  # a fresh run reports "running" this long before its Result appears

SCENARIO = Scenario.model_validate_json((FIXTURES / "f1_scenario.json").read_text(encoding="utf-8"))
RESULT_FAIL = Result.model_validate_json((FIXTURES / "f1_result_fail.json").read_text(encoding="utf-8"))
RESULT_PASS = Result.model_validate_json((FIXTURES / "f1_result_pass.json").read_text(encoding="utf-8"))


class Run(BaseModel):
    run_id: str
    status: str  # "running" | "complete"
    created_at: float
    scenario: Scenario
    result: Optional[Result] = None
    rerun_of: Optional[str] = None


class _Stored(BaseModel):
    run_id: str
    created_at: float
    result: Result
    rerun_of: Optional[str] = None


app = FastAPI(title="DriftGuard Mock Runner")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_runs: Dict[str, _Stored] = {}


def _store(result: Result, rerun_of: Optional[str] = None, created_at: Optional[float] = None) -> _Stored:
    run = _Stored(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        created_at=created_at if created_at is not None else time.time(),
        result=result,
        rerun_of=rerun_of,
    )
    _runs[run.run_id] = run
    return run


def _view(stored: _Stored) -> Run:
    done = time.time() - stored.created_at >= RUNNING_SECONDS
    return Run(
        run_id=stored.run_id,
        status="complete" if done else "running",
        created_at=stored.created_at,
        scenario=SCENARIO,
        result=stored.result if done else None,
        rerun_of=stored.rerun_of,
    )


# Seed one finished red run so the dashboard has data on first load.
_store(RESULT_FAIL, created_at=time.time() - 60)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock": True}


@app.get("/runs", response_model=List[Run])
def list_runs() -> List[Run]:
    return [_view(r) for r in sorted(_runs.values(), key=lambda r: r.created_at, reverse=True)]


@app.post("/runs", response_model=Run, status_code=201)
def launch_run() -> Run:
    """Start a run. The mock always finds the F1 bug (red)."""
    return _view(_store(RESULT_FAIL))


@app.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    stored = _runs.get(run_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return _view(stored)


@app.post("/runs/{run_id}/rerun", response_model=Run, status_code=201)
def rerun(run_id: str) -> Run:
    """Re-run after a fix. The mock turns red into green (the before/after view)."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return _view(_store(RESULT_PASS, rerun_of=run_id))
