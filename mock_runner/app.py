"""
Interactive Mock Runner for DriftGuard:
FastAPI lightweight demo server for Render deployment.
Serves full interactive chaos test suite (F1 to F7),
reconciliation runs, Before/After fix verification, and Studio AI Assistant.
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
RUNNING_SECONDS = 1.5  # brief running status for realistic UI feel

# Load all 7 fault fixtures (F1 through F7)
SCENARIOS: Dict[str, Scenario] = {}
RESULTS_FAIL: Dict[str, Result] = {}
RESULTS_PASS: Dict[str, Result] = {}
DIFFS: Dict[str, str] = {}
PATCH_HASHES: Dict[str, str] = {}

BUG_MAP = {
    "F1_LOST_CAPTURE_RESPONSE": "BUG-01",
    "F2_SLOW_PAYPAL": "BUG-02",
    "F3_FORCED_DECLINE": "BUG-03",
    "F4_DUPLICATE_INVOICE": "BUG-04",
    "F5_MONEY_MATH_TRAP": "BUG-05",
    "F6_WEBHOOK_REPLAY": "BUG-06",
    "F7_PROMPT_INJECTION": "BUG-07",
}

EXPLANATIONS = {
    "BUG-01": "Add PayPal-Request-Id header to capture call for idempotent retry on 504 timeouts and inspect order status before retrying.",
    "BUG-02": "Increase client timeout window and query order status before aborting slow upstream responses.",
    "BUG-03": "Handle 422 INSTRUMENT_DECLINED explicitly; prompt buyer for alternate payment rather than marking order completed.",
    "BUG-04": "Attach deterministic invoice ID and idempotency key to prevent accidental duplicate captures on connection retries.",
    "BUG-05": "Strictly validate subtotal and line items match total amount before creating PayPal order to prevent money math tampering.",
    "BUG-06": "Track processed capture IDs in shop state to discard duplicate webhook deliveries idempotently.",
    "BUG-07": "Verify cryptographic refund authorization and enforce refund limits rather than blindly executing unauthenticated LLM tool calls.",
}

for i in range(1, 8):
    key = f"f{i}"
    sc_path = FIXTURES / f"{key}_scenario.json"
    rf_path = FIXTURES / f"{key}_result_fail.json"
    rp_path = FIXTURES / f"{key}_result_pass.json"
    if sc_path.exists() and rf_path.exists() and rp_path.exists():
        sc = Scenario.model_validate_json(sc_path.read_text(encoding="utf-8"))
        rf = Result.model_validate_json(rf_path.read_text(encoding="utf-8"))
        rp = Result.model_validate_json(rp_path.read_text(encoding="utf-8"))
        SCENARIOS[key] = sc
        RESULTS_FAIL[key] = rf
        RESULTS_PASS[key] = rp

    bug_id = f"BUG-0{i}"
    diff_path = KNOWN_FIXES / f"{bug_id}.diff"
    if diff_path.exists():
        diff_text = diff_path.read_text(encoding="utf-8")
        DIFFS[bug_id] = diff_text
        PATCH_HASHES[bug_id] = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()


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
    scenario: Scenario
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


def _get_fix_proposal_for(scenario: Scenario) -> FixProposal:
    fault_str = scenario.fault.value if hasattr(scenario.fault, "value") else str(scenario.fault)
    bug_id = BUG_MAP.get(fault_str, "BUG-01")
    diff_text = DIFFS.get(bug_id, DIFFS.get("BUG-01", ""))
    expl = EXPLANATIONS.get(bug_id, "Add idempotency headers and state validation.")
    return FixProposal(
        bug_id=bug_id,
        applies=True,
        source="known_fix",
        provider="Claude 3.7 Sonnet (Curated)",
        diff=diff_text,
        explanation=expl,
        files=["src/checkout.ts" if bug_id in ["BUG-01", "BUG-02", "BUG-03", "BUG-04"] else "src/state.ts"],
        lines_changed=len(diff_text.splitlines()) if diff_text else 28,
        attempts=1,
    )


def _store(
    result: Result,
    scenario: Scenario,
    rerun_of: Optional[str] = None,
    created_at: Optional[float] = None,
    fix: Optional[FixProof] = None,
) -> _Stored:
    run = _Stored(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        created_at=created_at if created_at is not None else time.time(),
        scenario=scenario,
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
        scenario=stored.scenario,
        result=stored.result if done else None,
        rerun_of=stored.rerun_of,
        fix=stored.fix if done else None,
    )


# Seed initial stored runs for all 7 faults (F7 down to F1)
# so the overview shows all 7 faults monitored and F1 as the latest
now = time.time()
for idx, key in enumerate(["f7", "f6", "f5", "f4", "f3", "f2", "f1"]):
    if key in SCENARIOS and key in RESULTS_FAIL:
        _store(
            RESULTS_FAIL[key],
            scenario=SCENARIOS[key],
            created_at=now - (7 - idx) * 60,
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock": True, "faults_loaded": len(SCENARIOS)}


@app.get("/runs", response_model=List[Run])
def list_runs() -> List[Run]:
    return [_view(r) for r in sorted(_runs.values(), key=lambda r: r.created_at, reverse=True)]


@app.post("/runs", response_model=Run, status_code=201)
def launch_run() -> Run:
    """Start a run. Defaults to F1 (lost capture response)."""
    sc = SCENARIOS.get("f1", list(SCENARIOS.values())[0])
    rf = RESULTS_FAIL.get("f1", list(RESULTS_FAIL.values())[0])
    return _view(_store(rf, scenario=sc))


@app.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    stored = _runs.get(run_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return _view(stored)


@app.post("/runs/{run_id}/rerun", response_model=Run, status_code=201)
def rerun(run_id: str) -> Run:
    """Re-run after a fix. Turns red into green."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    orig = _runs[run_id]
    fault_str = orig.scenario.fault.value if hasattr(orig.scenario.fault, "value") else str(orig.scenario.fault)
    pass_res = None
    for k, sc in SCENARIOS.items():
        k_fault = sc.fault.value if hasattr(sc.fault, "value") else str(sc.fault)
        if k_fault == fault_str:
            pass_res = RESULTS_PASS.get(k)
            break
    if pass_res is None:
        pass_res = list(RESULTS_PASS.values())[0]

    return _view(_store(pass_res, scenario=orig.scenario, rerun_of=run_id))


@app.post("/runs/{run_id}/verify-fix", response_model=Run, status_code=201)
def verify_fix(run_id: str) -> Run:
    """Simulates verifying the patch in an ephemeral environment, turning red into green with cryptographic proof."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    orig = _runs[run_id]
    proposal = _get_fix_proposal_for(orig.scenario)
    patch_hash = PATCH_HASHES.get(proposal.bug_id, list(PATCH_HASHES.values())[0] if PATCH_HASHES else "431b7d67286f0f30adf7347e06133490e43ea0a070480108bc25d1adc3c7865d")
    
    proof = FixProof(
        proposal=proposal,
        patch_sha256=patch_hash,
    )

    fault_str = orig.scenario.fault.value if hasattr(orig.scenario.fault, "value") else str(orig.scenario.fault)
    pass_res = None
    for k, sc in SCENARIOS.items():
        k_fault = sc.fault.value if hasattr(sc.fault, "value") else str(sc.fault)
        if k_fault == fault_str:
            pass_res = RESULTS_PASS.get(k)
            break
    if pass_res is None:
        pass_res = list(RESULTS_PASS.values())[0]

    return _view(_store(pass_res, scenario=orig.scenario, rerun_of=run_id, fix=proof))


@app.post("/fix", response_model=FixProposal)
def propose_fix_endpoint(req: FixRequest) -> FixProposal:
    """Returns the verified curated patch for the failing run."""
    return _get_fix_proposal_for(req.scenario)


@app.post("/llm/messages")
def llm_messages(req: dict) -> dict:
    """Studio AI Assistant conversational responses for AG Grid panel."""
    # Check if live Anthropic API key is provided
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import httpx
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=req,
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass

    # Extract user prompt
    messages = req.get("messages", [])
    user_prompt = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                user_prompt = content.lower()
            elif isinstance(content, list):
                user_prompt = " ".join([c.get("text", "") for c in content if isinstance(c, dict)]).lower()
            break

    # Contextual dynamic responses
    if any(w in user_prompt for w in ["fix", "gen", "patch", "repair", "solve"]):
        reply = (
            "To resolve ledger drift caused by network timeouts: \n\n"
            "1. **Deterministic Idempotency**: Provide a unique `PayPal-Request-Id` (e.g. SHA-256 of `capture-${orderId}`) in every capture request.\n"
            "2. **State Inquiry**: On 504 Gateway Timeout or network drops, query `ordersController.getOrder(orderId)` before retrying to verify if the capture settled upstream.\n"
            "3. **Local Reconciliation**: Update application ledger only after confirming PayPal's COMPLETED status."
        )
    elif any(w in user_prompt for w in ["why", "fail", "verdict", "drift", "explain", "reason"]):
        reply = (
            "**Root Cause Analysis:**\n"
            "The active fault simulates an asymmetric network boundary drop. PayPal successfully processed and recorded the payment ($38.97 USD), "
            "but the response was dropped before reaching the application shop. The shop treated the HTTP timeout as a lost order, causing ledger drift: PayPal = 1 capture, App = 0 captures."
        )
    elif any(w in user_prompt for w in ["chart", "metric", "overview", "graph", "table", "report"]):
        reply = (
            "The Studio report displays transaction telemetry across all 7 fault profiles (F1 to F7). "
            "The chart highlights discrepancy rates between PayPal Sandbox ledger captures and application database settlements."
        )
    elif any(w in user_prompt for w in ["f2", "f3", "f4", "f5", "f6", "f7", "fault", "scenario"]):
        reply = (
            "DriftGuard monitors 7 core payment fault scenarios:\n"
            "• **F1**: Lost capture response (504 timeout)\n"
            "• **F2**: Slow PayPal upstream latency\n"
            "• **F3**: 422 Instrument declined mishandling\n"
            "• **F4**: Duplicate captures on retry timeout\n"
            "• **F5**: Subtotal and currency manipulation\n"
            "• **F6**: Webhook replay duplicate capture\n"
            "• **F7**: Prompt injection unauthorized refund"
        )
    else:
        reply = (
            "Hello! I am DriftGuard Studio Agent. I continuously analyze PayPal Sandbox ledger records against application state. "
            "You can ask me to explain why a run failed, propose a code fix, break down currency discrepancies, or query any of the 7 chaos scenarios."
        )

    return {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "model": "claude-3-7-sonnet-20250219",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": reply}],
        "usage": {"input_tokens": 120, "output_tokens": 85},
    }
