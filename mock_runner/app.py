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
import threading
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
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

# Accurate mapping to seeded bug catalog (targets/demo-shop/bugs.yaml)
BUG_MAP = {
    "F1_LOST_CAPTURE_RESPONSE": "BUG-01",
    "F2_SLOW_PAYPAL": "BUG-02",
    "F3_FORCED_DECLINE": "BUG-03",
    "F4_DUPLICATE_INVOICE": "BUG-04",
    "F5_MONEY_MATH_TRAP": "BUG-05",
    "F6_WEBHOOK_REPLAY": "BUG-09",
    "F7_PROMPT_INJECTION": "BUG-10",
}

BUG_FILES = {
    "BUG-01": ["src/checkout.ts"],
    "BUG-02": ["src/checkout.ts"],
    "BUG-03": ["src/checkout.ts"],
    "BUG-04": ["src/checkout.ts"],
    "BUG-05": ["src/checkout.ts"],
    "BUG-06": ["src/checkout.ts"],
    "BUG-07": ["src/checkout.ts"],
    "BUG-08": ["src/webhooks.ts"],
    "BUG-09": ["src/webhooks.ts"],
    "BUG-10": ["src/assistant.ts"],
}

EXPLANATIONS = {
    "BUG-01": "Add PayPal-Request-Id header to capture call for idempotent retry on 504 timeouts and inspect order status before retrying.",
    "BUG-02": "Increase client timeout window and query order status before aborting slow upstream responses.",
    "BUG-03": "Handle 422 INSTRUMENT_DECLINED explicitly; prompt buyer for alternate payment rather than marking order completed.",
    "BUG-04": "Attach deterministic invoice ID and idempotency key to prevent accidental duplicate captures on connection retries.",
    "BUG-05": "Strictly validate sales tax and line items using integer minor units or Decimal arithmetic to prevent floating-point rounding drift.",
    "BUG-06": "Strictly validate coupon discount calculation across purchase unit amounts and item totals.",
    "BUG-07": "Round zero-decimal currencies (JPY/KRW) to whole integers without fractional cents.",
    "BUG-08": "Verify transmission signature with PayPal API before accepting incoming webhooks.",
    "BUG-09": "Check shopState.hasWebhookEvent(event.id) before processing to discard duplicate webhook deliveries idempotently.",
    "BUG-10": "Enforce deterministic policy guardrail on refunds (role check + max refund limit) rather than blindly executing chat assistant instructions.",
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

for i in range(1, 11):
    bug_id = f"BUG-{i:02d}"
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
    mode: str = "sample"


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
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_runs: Dict[str, _Stored] = {}
_ai_lock = threading.Lock()
_ai_calls_total = 0
_ai_calls_by_ip = defaultdict(deque)
MAX_AI_CALLS_PER_PROCESS = 100
MAX_AI_CALLS_PER_IP_HOUR = 30


def _get_fix_proposal_for(scenario: Scenario) -> FixProposal:
    fault_str = scenario.fault.value if hasattr(scenario.fault, "value") else str(scenario.fault)
    bug_id = BUG_MAP.get(fault_str, "BUG-01")
    diff_text = DIFFS.get(bug_id, DIFFS.get("BUG-01", ""))
    expl = EXPLANATIONS.get(bug_id, "Add idempotency headers and state validation.")
    files = BUG_FILES.get(bug_id, ["src/checkout.ts"])
    return FixProposal(
        bug_id=bug_id,
        applies=True,
        source="known_fix",
        provider=None,
        diff=diff_text,
        explanation=expl,
        files=files,
        lines_changed=len(diff_text.splitlines()),
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
    return {"status": "ok", "mock": True, "faults_loaded": len(SCENARIOS), "model_ready": bool(os.getenv("ANTHROPIC_API_KEY") and os.getenv("DRIFTGUARD_PUBLIC_AI_ENABLED") == "1")}


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
    """Show the prepared PASS fixture beside a FAIL fixture; no patch or PayPal call runs here."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    orig = _runs[run_id]
    proposal = _get_fix_proposal_for(orig.scenario)
    patch_hash = PATCH_HASHES.get(
        proposal.bug_id,
        list(PATCH_HASHES.values())[0] if PATCH_HASHES else "431b7d67286f0f30adf7347e06133490e43ea0a070480108bc25d1adc3c7865d"
    )
    
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
    """Returns a prepared curated patch; the hosted preview does not apply it."""
    return _get_fix_proposal_for(req.scenario)


@app.post("/llm/messages")
def llm_messages(req: dict, request: Request) -> dict:
    """A bounded model call when enabled; otherwise a clearly identified preview reply."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and os.getenv("DRIFTGUARD_PUBLIC_AI_ENABLED") == "1":
        messages = req.get("messages")
        tools = req.get("tools", [])
        if not isinstance(messages, list) or not messages or len(messages) > 24:
            raise HTTPException(413, "Studio requires 1–24 messages")
        if not isinstance(tools, list) or len(tools) > 20 or len(json.dumps(req)) > 40_000:
            raise HTTPException(413, "Studio request is too large")
        client_ip = request.client.host if request.client else "unknown"
        global _ai_calls_total
        with _ai_lock:
            recent = _ai_calls_by_ip[client_ip]
            while recent and recent[0] < time.monotonic() - 3600:
                recent.popleft()
            if _ai_calls_total >= MAX_AI_CALLS_PER_PROCESS or len(recent) >= MAX_AI_CALLS_PER_IP_HOUR:
                raise HTTPException(429, "Studio model call limit reached")
            _ai_calls_total += 1
            recent.append(time.monotonic())
        try:
            import httpx
            payload = {
                "model": os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
                "max_tokens": min(max(int(req.get("max_tokens", 1024)), 1), 2048),
                "messages": messages,
            }
            if isinstance(req.get("system"), str):
                payload["system"] = req["system"]
            if tools:
                payload["tools"] = tools
                if isinstance(req.get("tool_choice"), dict):
                    payload["tool_choice"] = req["tool_choice"]
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code == 200:
                    return resp.json()
                raise HTTPException(502, f"Anthropic returned HTTP {resp.status_code}")
        except HTTPException:
            raise
        except (ValueError, TypeError):
            raise HTTPException(422, "Invalid Studio token limit") from None
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Anthropic request failed: {type(exc).__name__}") from exc

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

    # Contextual dynamic responses based on exact fault mentioned
    if "f7" in user_prompt or "refund" in user_prompt or "injection" in user_prompt:
        reply = (
            "**Fault F7 Analysis (Prompt Injection & Unauthorized Refund):**\n"
            "The AI customer support assistant executed an unauthenticated refund tool call without cryptographic authorization or role verification. "
            "The proposed BUG-10 patch in `src/assistant.ts` adds a deterministic policy limit ($15.00 max) and admin role check. This scenario uses a simulated shop-state refund."
        )
    elif "f6" in user_prompt or "webhook" in user_prompt or "replay" in user_prompt:
        reply = (
            "**Fault F6 Analysis (Webhook Replay Duplicate):**\n"
            "A replayed PayPal webhook event (`PAYMENT.CAPTURE.COMPLETED`) was delivered multiple times. Because event deduplication was missing, the shop double-recorded captures. "
            "The BUG-09 patch in `src/webhooks.ts` checks `shopState.hasWebhookEvent(event.id)`. Capture-level deduplication still needs live verification."
        )
    elif "f5" in user_prompt or "tax" in user_prompt or "math" in user_prompt or "money" in user_prompt:
        reply = (
            "**Fault F5 Analysis (Money Math Trap):**\n"
            "Floating-point tax rounding caused a 4-cent discrepancy ($38.92 observed vs $38.96 expected). "
            "The proposed BUG-05 patch in `src/checkout.ts` uses integer minor units or exact Decimal arithmetic; the hosted preview has not rerun it."
        )
    elif "f4" in user_prompt or "invoice" in user_prompt:
        reply = (
            "**Fault F4 Analysis (Duplicate Invoice / Non-Deterministic Invoice ID):**\n"
            "Invoice IDs generated using non-deterministic seeds caused invoice collision errors on retry. "
            "The fix (BUG-04 in `src/checkout.ts`) derives deterministic invoice IDs from stable cart content hashes."
        )
    elif "f3" in user_prompt or "decline" in user_prompt:
        reply = (
            "**Fault F3 Analysis (Forced Decline / 422 INSTRUMENT_DECLINED):**\n"
            "When PayPal returned 422 INSTRUMENT_DECLINED, the unpatched app mistakenly marked the order completed. "
            "The fix (BUG-03 in `src/checkout.ts`) surfaces payment failure and keeps the order unpaid."
        )
    elif "f2" in user_prompt or "slow" in user_prompt:
        reply = (
            "**Fault F2 Analysis (Slow PayPal Upstream Latency):**\n"
            "Upstream delays caused client timeout aborts without idempotent keys, creating unlinked duplicate orders on retry. "
            "The fix (BUG-02 in `src/checkout.ts`) passes a stable PayPal-Request-Id across order creation retries."
        )
    elif any(w in user_prompt for w in ["fix", "gen", "patch", "repair", "solve"]):
        reply = (
            "**Recommended Fix (Fault F1 - Lost Capture Response):**\n"
            "1. Attach a deterministic `PayPal-Request-Id` (SHA-256 of `capture-${orderId}`) to the capture request.\n"
            "2. On 504 Gateway Timeout or network drops, query `ordersController.getOrder(orderId)` before retrying to check if the capture settled upstream.\n"
            "3. Only update shop state when COMPLETED status is confirmed by PayPal."
        )
    elif any(w in user_prompt for w in ["why", "fail", "verdict", "drift", "explain", "reason"]):
        reply = (
            "**Root Cause Analysis (Fault F1):**\n"
            "An asymmetric network boundary drop occurred after PayPal successfully captured the buyer's funds ($38.97 USD). "
            "The application shop received a 504 Gateway Timeout and never credited the order in its database, causing ledger drift (PayPal = 1 capture, App = 0 captures)."
        )
    elif any(w in user_prompt for w in ["chart", "metric", "overview", "graph", "table", "report"]):
        reply = (
            "The Studio canvas tracks transaction telemetry across all 7 fault profiles (F1 to F7). "
            "Discrepancies between PayPal Sandbox ledger captures and application database records are flagged in red."
        )
    else:
        reply = (
            "Hello! I am DriftGuard Studio Agent. I continuously reconcile PayPal Sandbox ledger records against application database state. "
            "You can ask me to explain why any fault failed (F1 through F7), inspect currency math, or review code patches."
        )

    return {
        "id": f"preview_{uuid.uuid4().hex[:8]}",
        "model": "driftguard-preview",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "Sample answer from prepared scenario notes; no Claude call was made.\n\n" + reply}],
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }
