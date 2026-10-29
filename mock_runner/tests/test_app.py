"""Mock runner tests: endpoints work and every Result matches the contracts."""

import time

import pytest
from fastapi.testclient import TestClient

from contracts import Result, Verdict
from mock_runner import app as mock_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mock_app, "RUNNING_SECONDS", 0.0)
    return TestClient(mock_app.app)


def test_seeded_run_is_red_and_contract_valid(client):
    runs = client.get("/runs").json()
    assert runs and runs[0]["status"] == "complete"
    result = Result.model_validate(runs[0]["result"])
    assert result.verdict == Verdict.FAIL
    assert result.evidence.paypal_capture_ids


def test_launch_then_get(client):
    created = client.post("/runs")
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    got = client.get(f"/runs/{run_id}").json()
    assert Result.model_validate(got["result"]).verdict == Verdict.FAIL
    assert got["scenario"]["fault"] == "F1_LOST_CAPTURE_RESPONSE"


def test_rerun_turns_red_into_green(client):
    run_id = client.post("/runs").json()["run_id"]
    again = client.post(f"/runs/{run_id}/rerun").json()
    assert again["rerun_of"] == run_id
    assert Result.model_validate(again["result"]).verdict == Verdict.PASS


def test_running_state_hides_result(monkeypatch):
    monkeypatch.setattr(mock_app, "RUNNING_SECONDS", 60.0)
    client = TestClient(mock_app.app)
    run = client.post("/runs").json()
    assert run["status"] == "running" and run["result"] is None


def test_unknown_run_is_404(client):
    assert client.get("/runs/nope").status_code == 404
    assert client.post("/runs/nope/rerun").status_code == 404
