"""The API may claim a fix only after storing the patch used for a real rerun."""

import importlib
import sqlite3

from fastapi.testclient import TestClient

from ai.fixer.fixer import FixProposal
from contracts import Result, Scenario
from engine.api import main
database = importlib.import_module("engine.orchestrator.db")


def test_existing_sqlite_runs_migrate_and_keep_fix_provenance(tmp_path, monkeypatch):
    path = tmp_path / "runs.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, status TEXT, created_at REAL, "
                     "scenario_json TEXT, result_json TEXT, rerun_of TEXT)")
    monkeypatch.setattr(database, "SQLITE_DB_PATH", path)
    monkeypatch.setattr(database.db, "use_postgres", False)
    database.db.init_db()
    with sqlite3.connect(path) as conn:
        assert "fix_json" in {row[1] for row in conn.execute("PRAGMA table_info(runs)")}

    scenario = Scenario.model_validate_json((main.FIXTURES / "f1_scenario.json").read_text())
    failed = Result.model_validate_json((main.FIXTURES / "f1_result_fail.json").read_text())
    passed = Result.model_validate_json((main.FIXTURES / "f1_result_pass.json").read_text())
    database.db.create_run("parent", scenario.model_dump())
    database.db.update_run_result("parent", "complete", failed.model_dump())
    monkeypatch.setenv("DRIFTGUARD_ENABLE_FIX_RERUN", "1")

    def fake_verify(received_scenario, received_failure, record):
        assert received_scenario == scenario
        assert received_failure == failed
        record(FixProposal(bug_id="BUG-01", applies=True, source="known_fix",
                           provider=None, diff="patch", explanation=None, files=["src/checkout.ts"],
                           lines_changed=1, attempts=1, error=None), "a" * 64)
        return passed

    monkeypatch.setattr("ai.fixer.verify_run.generate_and_verify", fake_verify)
    with TestClient(main.app) as client:
        response = client.post("/runs/parent/verify-fix")
        assert response.status_code == 201
        child_id = response.json()["run_id"]
        child = client.get(f"/runs/{child_id}").json()
        assert child["rerun_of"] == "parent"
        assert child["result"]["verdict"] == "PASS"
        assert child["fix"]["patch_sha256"] == "a" * 64
        assert child["fix"]["proposal"]["diff"] == "patch"
        assert any(run["run_id"] == child_id and run["fix"] for run in client.get("/runs").json())
        assert client.post(f"/runs/{child_id}/verify-fix").status_code == 422


def test_fix_execution_is_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "runs.db")
    monkeypatch.setattr(database.db, "use_postgres", False)
    monkeypatch.delenv("DRIFTGUARD_ENABLE_FIX_RERUN", raising=False)
    with TestClient(main.app) as client:
        assert client.post("/runs/nonexistent/verify-fix").status_code == 503


def test_both_local_frontend_hostnames_can_read_the_api(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "runs.db")
    monkeypatch.setattr(database.db, "use_postgres", False)
    with TestClient(main.app) as client:
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            response = client.options("/runs", headers={
                "Origin": origin, "Access-Control-Request-Method": "GET",
            })
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
