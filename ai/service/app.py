"""
AI service: the one place model keys live. The dashboard's Studio agent sends its turns here and
never sees a key.

    python -m uvicorn ai.service.app:app --port 8001

POST /llm/messages takes an Anthropic Messages request body (system, messages, tools, tool_choice,
max_tokens) and returns the model's reply. The model is fixed on the server, output is capped, the
request size is limited, and every call goes through the spend guard.
Planner Ref: Part 8 (Studio agent skeleton, Wed 4 Nov).
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai.common.providers import DEFAULT_MODELS, SpendGuard, _key, cost_usd

MAX_OUTPUT_TOKENS = 2048
MAX_INPUT_CHARS = 200_000
MAX_TOOLS = 40
DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:3000"


class TurnRequest(BaseModel):
    system: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(..., min_length=1)
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_choice: Optional[Dict[str, Any]] = None
    max_tokens: int = Field(1024, ge=1)


class ModelBackend:
    """The Anthropic client plus its spend guard. Tests replace this with a fake."""

    def __init__(self, client: Any, model: str, guard: SpendGuard):
        self.client, self.model, self.guard = client, model, guard


def get_backend() -> Optional[ModelBackend]:
    key = _key("ANTHROPIC_API_KEY")
    if key is None:
        return None
    import anthropic

    return ModelBackend(
        anthropic.Anthropic(api_key=key),
        os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODELS["anthropic"],
        SpendGuard(float(os.getenv("ANTHROPIC_SPEND_LIMIT_USD", "1.50"))),
    )


app = FastAPI(title="DriftGuard AI service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("DRIFTGUARD_CORS_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health(backend: Optional[ModelBackend] = Depends(get_backend)):
    return {
        "status": "ok",
        "model_ready": backend is not None,
        "spend_left_usd": None if backend is None else round(max(backend.guard.limit_usd - backend.guard.spent_usd, 0), 4),
    }


@app.post("/llm/messages")
def llm_messages(req: TurnRequest, backend: Optional[ModelBackend] = Depends(get_backend)):
    if backend is None:
        raise HTTPException(503, "No model key on the server: set ANTHROPIC_API_KEY in .env")
    if len(req.tools) > MAX_TOOLS:
        raise HTTPException(413, f"Too many tools ({len(req.tools)} > {MAX_TOOLS})")
    if len(repr(req.messages)) + len(req.system or "") + len(repr(req.tools)) > MAX_INPUT_CHARS:
        raise HTTPException(413, "Request too large")
    if not backend.guard.allow():
        raise HTTPException(429, f"Spend limit ${backend.guard.limit_usd:.2f} reached")

    body: Dict[str, Any] = {
        "model": backend.model,
        "max_tokens": min(req.max_tokens, MAX_OUTPUT_TOKENS),
        "messages": req.messages,
    }
    if req.system:
        body["system"] = req.system
    if req.tools:
        body["tools"] = req.tools
        if req.tool_choice:
            body["tool_choice"] = req.tool_choice

    import anthropic

    try:
        msg = backend.client.messages.create(**body)
    except anthropic.APIError as exc:
        raise HTTPException(502, f"Model call failed: {type(exc).__name__}") from exc

    backend.guard.add(cost_usd(backend.model, msg.usage.input_tokens, msg.usage.output_tokens))
    content = [block.model_dump(mode="json", exclude_none=True) for block in msg.content]
    return {
        "id": msg.id,
        "model": msg.model,
        "stop_reason": msg.stop_reason,
        "content": content,
        "usage": {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens},
    }
