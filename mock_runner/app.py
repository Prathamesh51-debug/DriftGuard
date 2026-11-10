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

import os
import json
import time
import uuid
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contracts import Result, Scenario

FIXTURES = Path(__file__).resolve().parents[1] / "contracts" / "fixtures"
KNOWN_FIXES = Path(__file__).resolve().parents[1] / "ai" / "fixer" / "known_fixes"
RUNNING_SECONDS = 1.5  # a fresh run reports "running" this long before its Result appears

SCENARIO = Scenario.model_validate_json((FIXTURES / "f1_scenario.json").read_text(encoding="utf-8"))
RESULT_FAIL = Result.model_validate_json((FIXTURES / "f1_result_fail.json").read_text(encoding="utf-8"))
RESULT_PASS = Result.model_validate_json((FIXTURES / "f1_result_pass.json").read_text(encoding="utf-8"))

DIFF_BUG_01 = ""
if (KNOWN_FIXES / "BUG-01.diff").exists():
    DIFF_BUG_01 = (KNOWN_FIXES / "BUG-01.diff").read_text(encoding="utf-8")

PATCH_SHA256 = (
    hashlib.sha256(DIFF_BUG_01.encode("utf-8")).hexdigest()
    if DIFF_BUG_01
    else "431b7d67286f0f30adf7347e06133490e43ea0a070480108bc25d1adc3c7865d"
)


class FixRequest(BaseModel):
    scenario: Scenario
    result: Result


class FixProposal(BaseModel):
    bug_id: str
    applies: bool
    source: str
    provider: Optional[str] = None
    diff: Optional[str] = None
    explanation: Optional[str] = None
    files: List[str] = []
    lines_changed: int = 0
    attempts: int = 1
    error: Optional[str] = None


class FixProof(BaseModel):
    proposal: FixProposal
    patch_sha256: str


class Run(BaseModel):
    run_id: str
    status: str  # "running" | "complete"
    created_at: float
    scenario: Scenario
    result: Optional[Result] = None
    rerun_of: Optional[str] = None
    fix: Optional[FixProof] = None


class _Stored(BaseModel):
    run_id: str
    created_at: float
    result: Result
    rerun_of: Optional[str] = None
    fix: Optional[FixProof] = None


app = FastAPI(title="DriftGuard Interactive Demo API")

cors_origins_env = os.getenv("DRIFTGUARD_CORS_ORIGINS", "")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://driftguard-dashboard.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
    allow_origin_regex=r"https://.*\.onrender\.com" if "*" not in allowed_origins else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_runs: Dict[str, _Stored] = {}


def _get_fix_proposal() -> FixProposal:
    return FixProposal(
        bug_id="BUG-01",
        applies=True,
        source="known_fix",
        provider="Claude 3.7 Sonnet (Curated)",
        diff=DIFF_BUG_01,
        explanation="Add PayPal-Request-Id header to capture order call to ensure idempotent retry and prevent duplicate charges on 504 timeouts.",
        files=["src/checkout.ts"],
        lines_changed=len(DIFF_BUG_01.splitlines()) if DIFF_BUG_01 else 28,
        attempts=1,
    )


def _store(
    result: Result,
    rerun_of: Optional[str] = None,
    created_at: Optional[float] = None,
    fix: Optional[FixProof] = None,
) -> _Stored:
    run = _Stored(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        created_at=created_at if created_at is not None else time.time(),
        result=result,
        rerun_of=rerun_of,
        fix=fix,
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
        fix=stored.fix if done else None,
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


@app.post("/runs/{run_id}/verify-fix", response_model=Run, status_code=201)
def verify_fix(run_id: str) -> Run:
    """Simulates verifying the patch in an ephemeral environment, turning red into green."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    proof = FixProof(
        proposal=_get_fix_proposal(),
        patch_sha256=PATCH_SHA256,
    )
    return _view(_store(RESULT_PASS, rerun_of=run_id, fix=proof))


@app.post("/fix", response_model=FixProposal)
def propose_fix_endpoint(req: FixRequest) -> FixProposal:
    """Returns the verified curated patch for the failing run."""
    return _get_fix_proposal()


@app.post("/llm/messages")
def llm_messages(req: dict) -> dict:
    """Studio AI Assistant conversational responses for AG Grid panel."""
    return {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "model": "claude-3-7-sonnet-20250219",
        "stop_reason": "end_turn",
        "content": [
            {
                "type": "text",
                "text": "Hello! I am DriftGuard Studio Agent. In this active run (Fault F1 - Lost Capture Response), PayPal successfully settled $38.97, but a dropped network response caused application ledger drift (PayPal=1, App=0). The recommended fix adds a deterministic idempotency key and order state inquiry before retrying.",
            }
        ],
        "usage": {"input_tokens": 120, "output_tokens": 75},
    }
