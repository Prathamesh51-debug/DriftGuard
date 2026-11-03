"""
DriftGuard Core Engine API Server.
Planner Ref: Role Playbook A (A4 - API & Deploy).
Replaces mock_runner on port 8000 and serves real execution runs backed by database persistence.
"""

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contracts import Result, Scenario
from engine.orchestrator import db, run_scenario

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
DEFAULT_SCENARIO = Scenario.model_validate_json(
    (FIXTURES / "f1_scenario.json").read_text(encoding="utf-8")
)
INITIAL_RESULT_FAIL = Result.model_validate_json(
    (FIXTURES / "f1_result_fail.json").read_text(encoding="utf-8")
)


class Run(BaseModel):
    run_id: str
    status: str  # "running" | "complete"
    created_at: float
    scenario: Scenario
    result: Optional[Result] = None
    rerun_of: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    db.init_db()
    # If fresh database, seed one initial run so dashboard is populated on first launch
    existing = db.list_runs()
    if len(existing) == 0:
        seed_id = f"run_{uuid.uuid4().hex[:8]}"
        seed_run = db.create_run(seed_id, DEFAULT_SCENARIO.model_dump())
        db.update_run_result(seed_id, "complete", INITIAL_RESULT_FAIL.model_dump())
    yield


app = FastAPI(title="DriftGuard Engine API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _execute_run(run_id: str, scenario: Scenario):
    """Background task to run orchestrator and save real Result into database."""
    try:
        result = run_scenario(scenario)
        db.update_run_result(run_id, "complete", result.model_dump())
    except Exception as e:
        db.update_run_result(run_id, "complete", None)


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
    raw_runs = db.list_runs()
    return [
        Run(
            run_id=r["run_id"],
            status=r["status"],
            created_at=r["created_at"],
            scenario=Scenario.model_validate(r["scenario"]),
            result=Result.model_validate(r["result"]) if r.get("result") else None,
            rerun_of=r.get("rerun_of")
        )
        for r in raw_runs
    ]


@app.post("/runs", response_model=Run, status_code=201)
def launch_run(background_tasks: BackgroundTasks) -> Run:
    """Launch a real chaos test run on the target shop."""
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    db_run = db.create_run(run_id, DEFAULT_SCENARIO.model_dump())
    
    background_tasks.add_task(_execute_run, run_id, DEFAULT_SCENARIO)
    
    return Run(
        run_id=db_run["run_id"],
        status=db_run["status"],
        created_at=db_run["created_at"],
        scenario=DEFAULT_SCENARIO,
        result=None
    )


@app.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    r = db.get_run(run_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return Run(
        run_id=r["run_id"],
        status=r["status"],
        created_at=r["created_at"],
        scenario=Scenario.model_validate(r["scenario"]),
        result=Result.model_validate(r["result"]) if r.get("result") else None,
        rerun_of=r.get("rerun_of")
    )


@app.post("/runs/{run_id}/rerun", response_model=Run, status_code=201)
def rerun(run_id: str, background_tasks: BackgroundTasks) -> Run:
    """Trigger a rerun for a scenario."""
    parent = db.get_run(run_id)
    if not parent:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    new_run_id = f"run_{uuid.uuid4().hex[:8]}"
    scenario = Scenario.model_validate(parent["scenario"])
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
