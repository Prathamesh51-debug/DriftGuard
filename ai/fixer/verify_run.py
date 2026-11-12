"""Run a proposed fix against a disposable shop, then ask the engine for a verdict."""

import hashlib
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

import requests
from dotenv import load_dotenv

from contracts import Result, Scenario
from engine.orchestrator.runner import run_scenario
from evals.fixer.checks import CHECKS, check_patched

from . import apply_to_copy, find_bug, load_bugs, propose_fix
from .fixer import FixProposal
from .llm import LLMError
from .providers import OfflineLLM, llm_from_env


ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "targets/demo-shop"
SCRATCH = ROOT / "logs" / "verified-fix-scratch"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _safe_link(src, dst, *args, **kwargs):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst, *args, **kwargs)


def _stop_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def generate_and_verify(
    scenario: Scenario,
    failing: Result,
    on_proposal: Callable[[FixProposal, str], None],
) -> Result:
    """Generate on the server, validate, build and execute exactly that diff."""
    bug = find_bug(scenario, load_bugs())
    try:
        llm = llm_from_env(cache=False)
    except LLMError:
        llm = OfflineLLM()
    proposal = propose_fix(failing, scenario, bug, SHOP, llm)
    if not proposal.applies or not proposal.diff:
        raise RuntimeError(proposal.error or "The Fixer did not produce an applicable patch")

    load_dotenv(ROOT / ".env")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="run-", dir=SCRATCH) as scratch:
        copy = apply_to_copy(proposal.diff, SHOP, Path(scratch) / "shop")
        if bug.id in CHECKS:
            problems = check_patched(bug.id, (copy / bug.file).read_text(encoding="utf-8"))
            if problems:
                raise RuntimeError("Patch behavior check rejected it: " + "; ".join(problems))

        source_modules = SHOP / "node_modules"
        if not source_modules.is_dir():
            raise RuntimeError("Demo shop dependencies missing: npm install --prefix targets/demo-shop")
        shutil.copytree(source_modules, copy / "node_modules", copy_function=_safe_link)
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js is required to build the patched shop")
        build = subprocess.run(
            [node, str(copy / "node_modules/typescript/bin/tsc"), "-p", str(copy / "tsconfig.json")],
            cwd=copy, capture_output=True, text=True, timeout=90,
        )
        if build.returncode:
            raise RuntimeError("Patched shop did not compile: " + build.stderr[-1200:])

        sha256 = hashlib.sha256(proposal.diff.encode("utf-8")).hexdigest()
        on_proposal(proposal, sha256)
        port = _free_port()
        env = os.environ.copy()
        env.update(DEMO_SHOP_PORT=str(port), USE_PROXY="true", PROXY_HOST="127.0.0.1", PROXY_PORT="8080")
        kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(
            [node, str(copy / "node_modules/tsx/dist/cli.mjs"), str(copy / "src/server.ts")],
            cwd=copy, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **kwargs,
        )
        shop_url = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Patched shop exited before becoming healthy")
                try:
                    if requests.get(shop_url + "/health", timeout=0.5).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.25)
            else:
                raise RuntimeError("Patched shop did not become healthy")
            return run_scenario(scenario, target_shop_url=shop_url, scope_proxy_log=True)
        finally:
            _stop_tree(process)
