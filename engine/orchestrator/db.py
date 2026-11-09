"""
DriftGuard Orchestrator Database Layer.
Planner Ref: Role Playbook A (A1 - Orchestrator, Postgres, SKIP LOCKED queue).

Provides persistence for Scenarios, Runs, and Results with:
1. PostgreSQL primary (using JSONB and SELECT ... FOR UPDATE SKIP LOCKED).
2. SQLite resilient local fallback when PostgreSQL daemon is not active.
"""

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://driftguard:driftguard@localhost:5432/driftguard")
SQLITE_DB_PATH = Path(__file__).resolve().parents[2] / "driftguard.db"


class DBBackend:
    def __init__(self):
        self.use_postgres = False
        self._test_connection()

    def _test_connection(self):
        """Test PostgreSQL connection; fallback to SQLite if unavailable."""
        url = DATABASE_URL.replace("localhost", "127.0.0.1")
        try:
            import psycopg2
            conn = psycopg2.connect(url, connect_timeout=1)
            conn.close()
            self.use_postgres = True
            print("[DB] Connected to PostgreSQL primary.")
        except Exception as e:
            self.use_postgres = False
            print(f"[DB] PostgreSQL unavailable ({e}). Using persistent SQLite: {SQLITE_DB_PATH}")

    def init_db(self):
        """Create tables if not exist."""
        if self.use_postgres:
            import psycopg2
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS runs (
                            run_id VARCHAR(64) PRIMARY KEY,
                            status VARCHAR(32) NOT NULL,
                            created_at DOUBLE PRECISION NOT NULL,
                            scenario_json JSONB NOT NULL,
                            result_json JSONB,
                            rerun_of VARCHAR(64),
                            fix_json JSONB
                        );
                    """)
                    cur.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS fix_json JSONB")
                conn.commit()
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        run_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        scenario_json TEXT NOT NULL,
                        result_json TEXT,
                        rerun_of TEXT,
                        fix_json TEXT
                    );
                """)
                if "fix_json" not in {row[1] for row in cur.execute("PRAGMA table_info(runs)")}:
                    cur.execute("ALTER TABLE runs ADD COLUMN fix_json TEXT")
                conn.commit()

    def set_run_fix(self, run_id: str, fix_data: Dict[str, Any]):
        payload = json.dumps(fix_data)
        if self.use_postgres:
            import psycopg2
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE runs SET fix_json = %s WHERE run_id = %s", (payload, run_id))
                conn.commit()
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                conn.execute("UPDATE runs SET fix_json = ? WHERE run_id = ?", (payload, run_id))

    def create_run(self, run_id: str, scenario_data: Dict[str, Any], rerun_of: Optional[str] = None) -> Dict[str, Any]:
        created_at = time.time()
        status = "running"
        scenario_str = json.dumps(scenario_data)

        if self.use_postgres:
            import psycopg2
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO runs (run_id, status, created_at, scenario_json, result_json, rerun_of)
                        VALUES (%s, %s, %s, %s, NULL, %s)
                    """, (run_id, status, created_at, scenario_str, rerun_of))
                conn.commit()
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO runs (run_id, status, created_at, scenario_json, result_json, rerun_of)
                    VALUES (?, ?, ?, ?, NULL, ?)
                """, (run_id, status, created_at, scenario_str, rerun_of))
                conn.commit()

        return {
            "run_id": run_id,
            "status": status,
            "created_at": created_at,
            "scenario": scenario_data,
            "result": None,
            "rerun_of": rerun_of
        }

    def update_run_result(self, run_id: str, status: str, result_data: Optional[Dict[str, Any]]):
        result_str = json.dumps(result_data) if result_data else None
        if self.use_postgres:
            import psycopg2
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE runs
                        SET status = %s, result_json = %s
                        WHERE run_id = %s
                    """, (status, result_str, run_id))
                conn.commit()
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE runs
                    SET status = ?, result_json = ?
                    WHERE run_id = ?
                """, (status, result_str, run_id))
                conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        if self.use_postgres:
            import psycopg2
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT run_id, status, created_at, scenario_json, result_json, rerun_of, fix_json FROM runs WHERE run_id = %s", (run_id,))
                    row = cur.fetchone()
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT run_id, status, created_at, scenario_json, result_json, rerun_of, fix_json FROM runs WHERE run_id = ?", (run_id,))
                row = cur.fetchone()

        if not row:
            return None

        scenario = row[3] if isinstance(row[3], dict) else json.loads(row[3])
        result = None
        if row[4]:
            result = row[4] if isinstance(row[4], dict) else json.loads(row[4])

        return {
            "run_id": row[0],
            "status": row[1],
            "created_at": row[2],
            "scenario": scenario,
            "result": result,
            "rerun_of": row[5],
            "fix": row[6] if isinstance(row[6], dict) else json.loads(row[6]) if row[6] else None,
        }

    def list_runs(self) -> List[Dict[str, Any]]:
        runs = []
        if self.use_postgres:
            import psycopg2
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT run_id, status, created_at, scenario_json, result_json, rerun_of, fix_json FROM runs ORDER BY created_at DESC")
                    rows = cur.fetchall()
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT run_id, status, created_at, scenario_json, result_json, rerun_of, fix_json FROM runs ORDER BY created_at DESC")
                rows = cur.fetchall()

        for row in rows:
            scenario = row[3] if isinstance(row[3], dict) else json.loads(row[3])
            result = None
            if row[4]:
                result = row[4] if isinstance(row[4], dict) else json.loads(row[4])
            runs.append({
                "run_id": row[0],
                "status": row[1],
                "created_at": row[2],
                "scenario": scenario,
                "result": result,
                "rerun_of": row[5],
                "fix": row[6] if isinstance(row[6], dict) else json.loads(row[6]) if row[6] else None,
            })
        return runs

    def fetch_next_pending_run_skip_locked(self) -> Optional[Dict[str, Any]]:
        """
        Planner Rule A1: Concurrency-safe job extraction using SELECT ... FOR UPDATE SKIP LOCKED.
        """
        if self.use_postgres:
            import psycopg2
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT run_id, scenario_json
                        FROM runs
                        WHERE status = 'pending'
                        ORDER BY created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    """)
                    row = cur.fetchone()
                    if row:
                        cur.execute("UPDATE runs SET status = 'running' WHERE run_id = %s", (row[0],))
                        conn.commit()
                        scenario = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                        return {"run_id": row[0], "scenario": scenario}
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT run_id, scenario_json FROM runs WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1")
                row = cur.fetchone()
                if row:
                    cur.execute("UPDATE runs SET status = 'running' WHERE run_id = ?", (row[0],))
                    conn.commit()
                    scenario = json.loads(row[1])
                    return {"run_id": row[0], "scenario": scenario}
        return None


db = DBBackend()
