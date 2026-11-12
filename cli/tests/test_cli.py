"""CLI tests: exit codes, plain-words output and failure messages, against a fake engine and the real mock runner."""

import json
import socket
import threading
import time
from pathlib import Path

import pytest
import requests
import uvicorn

from cli.client import Engine
from cli.main import main

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
SCENARIO = json.loads((FIXTURES / "f1_scenario.json").read_text(encoding="utf-8"))
FAIL = json.loads((FIXTURES / "f1_result_fail.json").read_text(encoding="utf-8"))
PASS = json.loads((FIXTURES / "f1_result_pass.json").read_text(encoding="utf-8"))
ERROR = {**FAIL, "verdict": "ERROR", "rule": "target_reachable", "error_message": "HTTPConnectionPool(host='localhost', port=3001): refused"}


def run_json(run_id="run_aaaa1111", result=None, created_at=100.0, rerun_of=None, scenario=SCENARIO, fix=None):
    return {"run_id": run_id, "status": "complete" if result else "running", "created_at": created_at,
            "scenario": scenario, "result": result, "rerun_of": rerun_of, "fix": fix}


class Reply:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class FakeSession:
    """Answers by (method, path); a list of replies is consumed in order, the last one repeats."""

    def __init__(self, routes, error=None):
        self.routes, self.error, self.calls = routes, error, []

    def request(self, method, url, timeout=None, json=None):
        path = "/" + url.split("//", 1)[1].split("/", 1)[1]
        self.calls.append((method, path, json))
        if self.error:
            raise self.error
        reply = self.routes.get((method, path), (404, {}))
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        return Reply(*reply)


def cli(session, *argv):
    return main(list(argv), engine=Engine("http://engine.test", session))


def test_run_that_finds_a_problem_exits_1_and_prints_what_happened(capsys):
    s = FakeSession({("POST", "/runs"): (201, run_json(result=FAIL))})
    assert cli(s, "run") == 1
    out = capsys.readouterr().out
    assert "Verdict:   FAIL" in out
    assert FAIL["money_impact"] in out
    assert "App captures" in out and "PayPal captures" in out
    for oid in FAIL["evidence"]["paypal_order_ids"] + FAIL["evidence"]["paypal_capture_ids"]:
        assert oid in out


def test_run_that_passes_exits_0(capsys):
    s = FakeSession({("POST", "/runs"): (201, run_json(result=PASS))})
    assert cli(s, "run") == 0
    assert "Verdict:   PASS" in capsys.readouterr().out


def test_run_waits_for_the_result(monkeypatch, capsys):
    monkeypatch.setattr("cli.main.time.sleep", lambda s: None)
    s = FakeSession({
        ("POST", "/runs"): (201, run_json()),
        ("GET", "/runs/run_aaaa1111"): [(200, run_json()), (200, run_json()), (200, run_json(result=PASS))],
    })
    assert cli(s, "run") == 0
    assert [c[0] for c in s.calls].count("GET") == 3
    assert "Waiting for PayPal" in capsys.readouterr().err


def test_run_gives_up_with_exit_2_when_there_is_no_result_in_time(capsys):
    s = FakeSession({("POST", "/runs"): (201, run_json()), ("GET", "/runs/run_aaaa1111"): (200, run_json())})
    assert cli(s, "run", "--timeout", "0") == 2
    assert "Gave up" in capsys.readouterr().err


def test_no_wait_prints_the_current_state_without_polling(capsys):
    s = FakeSession({("POST", "/runs"): (201, run_json())})
    assert cli(s, "run", "--no-wait") == 2
    assert [c[0] for c in s.calls] == ["POST"]
    assert "No verdict yet" in capsys.readouterr().out


def test_an_unreachable_engine_says_how_to_start_it(capsys):
    s = FakeSession({}, error=requests.ConnectionError("refused"))
    assert cli(s, "run") == 2
    err = capsys.readouterr().err
    assert "Can't reach the engine at http://engine.test" in err and "make api" in err


def test_asking_for_a_fault_the_engine_did_not_run_is_an_error_not_a_silent_f1(capsys):
    s = FakeSession({("POST", "/runs"): (201, run_json(result=FAIL))})
    assert cli(s, "run", "--fault", "F3_FORCED_DECLINE") == 2
    assert s.calls[0][2] == {"fault": "F3_FORCED_DECLINE"}
    assert "asked for F3_FORCED_DECLINE" in capsys.readouterr().err


def test_short_fault_code_resolves_to_the_full_engine_fault(capsys):
    s = FakeSession({("POST", "/runs"): (201, run_json(result=FAIL))})
    assert cli(s, "run", "F1") == 1
    assert s.calls[0][2] == {"fault": "F1_LOST_CAPTURE_RESPONSE"}


def test_verified_run_report_preserves_patch_identity(capsys):
    fix = {"patch_sha256": "a" * 64, "proposal": {"bug_id": "BUG-01", "source": "known_fix"}}
    s = FakeSession({("GET", "/runs/run_ab12cd34"): (200, run_json("run_ab12cd34", PASS, fix=fix))})
    assert cli(s, "report", "ab12cd34") == 0
    out = capsys.readouterr().out
    assert "BUG-01 (known_fix)" in out and "a" * 64 in out


def test_an_errored_run_explains_itself_and_shows_no_numbers(capsys):
    s = FakeSession({("POST", "/runs"): (201, run_json(result=ERROR))})
    assert cli(s, "run") == 2
    out = capsys.readouterr().out
    assert "demo shop didn't answer" in out and "make demo" in out
    assert "PayPal captures" not in out and "HTTPConnectionPool" not in out


def test_report_defaults_to_the_newest_run(capsys):
    old, new = run_json("run_old00001", FAIL, created_at=1), run_json("run_new00002", PASS, created_at=2)
    s = FakeSession({("GET", "/runs"): (200, [old, new])})
    assert cli(s, "report") == 0
    assert "Run new00002" in capsys.readouterr().out


def test_report_accepts_a_short_id(capsys):
    s = FakeSession({("GET", "/runs/run_ab12cd34"): (200, run_json("run_ab12cd34", FAIL))})
    assert cli(s, "report", "ab12cd34") == 1
    assert s.calls[0][1] == "/runs/run_ab12cd34"


def test_report_all_lists_every_run_with_its_verdict(capsys):
    s = FakeSession({("GET", "/runs"): (200, [run_json("run_b0000002", PASS), run_json("run_a0000001", FAIL), run_json("run_c0000003", ERROR)])})
    assert cli(s, "report", "--all") == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].split() == ["RUN", "FAULT", "VERDICT", "PAYPAL/APP", "RESULT"]
    assert "b0000002" in out and "PASS" in out and "FAIL" in out and "ERROR" in out
    assert "refused" not in out


def test_report_json_is_valid_json(capsys):
    s = FakeSession({("GET", "/runs/run_ab12cd34"): (200, run_json("run_ab12cd34", FAIL))})
    cli(s, "report", "ab12cd34", "--json")
    assert json.loads(capsys.readouterr().out)["result"]["verdict"] == "FAIL"


def test_report_with_no_runs_says_how_to_start_one(capsys):
    s = FakeSession({("GET", "/runs"): (200, [])})
    assert cli(s, "report") == 2
    assert "python -m cli run" in capsys.readouterr().out


def test_report_for_an_unknown_run_is_a_clear_error(capsys):
    s = FakeSession({})
    assert cli(s, "report", "nope") == 2
    assert "/runs/run_nope" in capsys.readouterr().err


def test_a_reply_that_breaks_the_contract_is_reported_not_crashed(capsys):
    s = FakeSession({("POST", "/runs"): (201, {"run_id": "run_x", "status": "complete"})})
    assert cli(s, "run") == 2
    assert "does not match the contract" in capsys.readouterr().err


def test_engine_preserves_error_detail_on_http_failure():
    from cli.client import EngineError

    s = FakeSession({("POST", "/runs"): (422, {"detail": "Unknown fault 'FOO'. Valid values: ['F1']"})})
    engine = Engine("http://engine.test", s)
    with pytest.raises(EngineError, match="Unknown fault 'FOO'"):
        engine.launch("FOO")



# --- against the real mock runner over HTTP -------------------------------------------------

@pytest.fixture
def mock_engine():
    from mock_runner.app import app

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_end_to_end_against_the_mock_runner(mock_engine, capsys):
    assert main(["--api", mock_engine, "run", "--timeout", "30"]) == 1  # the mock always finds the F1 bug
    out = capsys.readouterr().out
    assert "Verdict:   FAIL" in out and "buyer charged" in out
    assert main(["--api", mock_engine, "report", "--all"]) == 0
    assert "FAIL" in capsys.readouterr().out
