"""
DriftGuard Core Engine API Server.
Planner Ref: Role Playbook A (A4 - API & Deploy).
Replaces mock_runner on port 8000 and serves real execution runs backed by database persistence.
"""

import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from contracts import Result, Scenario, Verdict, ObservedState, Evidence, FaultType
from engine.orchestrator import db, run_scenario

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
DEFAULT_SCENARIO = Scenario.model_validate_json(
    (FIXTURES / "f1_scenario.json").read_text(encoding="utf-8")
)

# Extra CORS origins (e.g. Render deploy URL) via env var.
# Format: comma-separated, e.g. "https://driftguard.onrender.com,https://staging.example.com"
_extra_origins = [
    o.strip() for o in os.getenv("DRIFTGUARD_CORS_ORIGINS", "").split(",") if o.strip()
]
CORS_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
] + _extra_origins


class Run(BaseModel):
    run_id: str
    status: str  # "running" | "complete" | "error"
    created_at: float
    scenario: Scenario
    result: Optional[Result] = None
    rerun_of: Optional[str] = None
    fix: Optional[dict] = None


class LaunchRunRequest(BaseModel):
    fault: Optional[str] = None  # FaultType value, e.g. "F1_LOST_CAPTURE_RESPONSE"


def _make_error_result(scenario: Scenario, exc: Exception) -> Result:
    """Build a well-formed ERROR Result for any unhandled engine exception."""
    return Result(
        scenario_id=scenario.scenario_id,
        verdict=Verdict.ERROR,
        rule="engine_run_completed",
        observed=ObservedState(captures=0, amount_captured="0.00"),
        evidence=Evidence(),
        money_impact="error: engine failed before reconciliation could finish",
        error_message=str(exc),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    db.init_db()
    # Mark any run left "running" from a previous crash as "error"
    # so the dashboard never shows a permanently-stuck RUNNING chip.
    for r in db.list_runs():
        if r["status"] == "running":
            error_result = Result(
                scenario_id=r["scenario"].get("scenario_id", "unknown"),
                verdict=Verdict.ERROR,
                rule="engine_run_completed",
                observed=ObservedState(captures=0, amount_captured="0.00"),
                evidence=Evidence(),
                money_impact="error: engine restarted during run",
                error_message="Engine process was restarted while this run was in progress.",
            )
            db.update_run_result(r["run_id"], "error", error_result.model_dump())
    yield


app = FastAPI(title="DriftGuard Engine API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _execute_run(run_id: str, scenario: Scenario):
    """Background task: run orchestrator and persist the Result (pass, fail, or error)."""
    try:
        result = run_scenario(scenario)
        db.update_run_result(run_id, "complete", result.model_dump())
    except Exception as e:
        error_result = _make_error_result(scenario, e)
        db.update_run_result(run_id, "error", error_result.model_dump())


def _execute_verified_run(run_id: str, scenario: Scenario, failing: Result):
    """Build a server-generated patch in a disposable shop and persist its proof."""
    from ai.fixer.verify_run import generate_and_verify

    try:
        def record_patch(proposal, patch_sha256: str):
            db.set_run_fix(run_id, {
                "proposal": proposal.model_dump(),
                "patch_sha256": patch_sha256,
            })

        result = generate_and_verify(scenario, failing, record_patch)
        db.update_run_result(run_id, "complete", result.model_dump())
    except Exception as exc:
        db.update_run_result(run_id, "error", _make_error_result(scenario, exc).model_dump())


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "engine": "live",
        "backend": "postgresql" if db.use_postgres else "sqlite",
        "timestamp": time.time()
    }


@app.get("/runs", response_model=List[Run])
def list_runs() -> List[Run]:
    runs: List[Run] = []
    for r in db.list_runs():
        try:
            runs.append(
                Run(
                    run_id=r["run_id"],
                    status=r["status"],
                    created_at=r["created_at"],
                    scenario=Scenario.model_validate(r["scenario"]),
                    result=Result.model_validate(r["result"]) if r.get("result") else None,
                    rerun_of=r.get("rerun_of"),
                    fix=r.get("fix"),
                )
            )
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            print(f"[API] Skipping invalid stored run {r.get('run_id')}: {exc}")
    return runs


@app.post("/runs", response_model=Run, status_code=201)
def launch_run(body: LaunchRunRequest = LaunchRunRequest(), background_tasks: BackgroundTasks = BackgroundTasks()) -> Run:
    """Launch a real chaos test run. Optional body: {"fault": "F1_LOST_CAPTURE_RESPONSE"}"""
    # Resolve which scenario to run
    if body.fault is not None:
        valid_faults = {f.value for f in FaultType}
        if body.fault not in valid_faults:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown fault '{body.fault}'. Valid values: {sorted(valid_faults)}"
            )
        # Load matching fixture by fault key prefix (e.g. "F2_SLOW_PAYPAL" -> "f2_scenario.json")
        fault_prefix = body.fault.split("_")[0].lower()  # "f1", "f2", etc.
        fixture_path = FIXTURES / f"{fault_prefix}_scenario.json"
        if not fixture_path.exists():
            raise HTTPException(
                status_code=422,
                detail=f"Fault '{body.fault}' has no fixture yet. Available: F1_LOST_CAPTURE_RESPONSE"
            )
        scenario = Scenario.model_validate_json(fixture_path.read_text(encoding="utf-8"))
    else:
        scenario = DEFAULT_SCENARIO

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    db_run = db.create_run(run_id, scenario.model_dump())

    background_tasks.add_task(_execute_run, run_id, scenario)

    return Run(
        run_id=db_run["run_id"],
        status=db_run["status"],
        created_at=db_run["created_at"],
        scenario=scenario,
        result=None
    )


@app.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    r = db.get_run(run_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    try:
        return Run(
            run_id=r["run_id"],
            status=r["status"],
            created_at=r["created_at"],
            scenario=Scenario.model_validate(r["scenario"]),
            result=Result.model_validate(r["result"]) if r.get("result") else None,
            rerun_of=r.get("rerun_of"),
            fix=r.get("fix"),
        )
    except (ValidationError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} contains malformed or incompatible legacy data: {exc}",
        )


@app.post("/runs/{run_id}/rerun", response_model=Run, status_code=201)
def rerun(run_id: str, background_tasks: BackgroundTasks) -> Run:
    """Trigger a rerun for a completed or errored scenario. Returns 409 if still running."""
    parent = db.get_run(run_id)
    if not parent:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if parent["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Run {run_id} is still running; wait for it to finish before rerunning."
        )

    try:
        scenario = Scenario.model_validate(parent["scenario"])
    except (ValidationError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} contains malformed or incompatible legacy data: {exc}",
        )
    new_run_id = f"run_{uuid.uuid4().hex[:8]}"
    db_run = db.create_run(new_run_id, scenario.model_dump(), rerun_of=run_id)

    background_tasks.add_task(_execute_run, new_run_id, scenario)

    return Run(
        run_id=db_run["run_id"],
        status=db_run["status"],
        created_at=db_run["created_at"],
        scenario=scenario,
        result=None,
        rerun_of=run_id
    )


@app.post("/runs/{run_id}/verify-fix", response_model=Run, status_code=201)
def verify_fix(run_id: str, background_tasks: BackgroundTasks) -> Run:
    """Generate and execute a patch. Explicitly opt in on trusted deployments."""
    if os.getenv("DRIFTGUARD_ENABLE_FIX_RERUN") != "1":
        raise HTTPException(status_code=503, detail="Patch execution is disabled on this engine")
    parent = db.get_run(run_id)
    if not parent:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if parent["status"] == "running":
        raise HTTPException(status_code=409, detail="Wait for the run to finish")
    try:
        failing = Result.model_validate(parent["result"]) if parent.get("result") else None
        scenario = Scenario.model_validate(parent["scenario"])
    except (ValidationError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} contains malformed or incompatible legacy data: {exc}",
        )
    if failing is None or failing.verdict != Verdict.FAIL:
        raise HTTPException(status_code=422, detail="Only failed runs can be fixed and verified")
    new_run_id = f"run_{uuid.uuid4().hex[:8]}"
    created = db.create_run(new_run_id, scenario.model_dump(), rerun_of=run_id)
    background_tasks.add_task(_execute_verified_run, new_run_id, scenario, failing)
    return Run(run_id=new_run_id, status=created["status"], created_at=created["created_at"],
               scenario=scenario, rerun_of=run_id)
