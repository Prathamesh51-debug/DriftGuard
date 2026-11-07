"""
Data models for the DriftGuard Code Scanner (ai/scanner).
Planner Ref: Part 9 (Role B3 Scanner).
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RiskType(str, Enum):
    MISSING_IDEMPOTENCY_KEY = "MISSING_IDEMPOTENCY_KEY"
    BLIND_RETRY_TIMEOUT = "BLIND_RETRY_TIMEOUT"
    UNHANDLED_DECLINE = "UNHANDLED_DECLINE"
    NON_DETERMINISTIC_INVOICE = "NON_DETERMINISTIC_INVOICE"
    FLOAT_ROUNDING = "FLOAT_ROUNDING"
    UNVERIFIED_WEBHOOK = "UNVERIFIED_WEBHOOK"
    DUPLICATE_WEBHOOK_PROCESSING = "DUPLICATE_WEBHOOK_PROCESSING"
    UNGUARDED_AI_REFUND = "UNGUARDED_AI_REFUND"


class CallSite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(..., description="Source file relative to project root")
    line: int = Field(..., ge=1, description="1-based line number")
    method: str = Field(..., description="Method name, route, or operation identified")
    has_idempotency_key: bool = Field(default=False, description="Whether PayPal-Request-Id is passed")
    risk_types: List[RiskType] = Field(default_factory=list, description="Identified financial drift risks")
    code_snippet: str = Field(..., description="Target source code line or snippet")
    notes: Optional[str] = Field(None, description="Diagnostic explanation of finding")


class FlowMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_path: str = Field(..., description="Target repository or directory scanned")
    call_sites: List[CallSite] = Field(default_factory=list, description="Identified PayPal call sites")
    total_sites: int = Field(..., ge=0, description="Total payment-related call sites identified")
    vulnerable_sites: int = Field(..., ge=0, description="Sites flagged with at least one financial drift risk")
    risk_summary: Dict[str, int] = Field(default_factory=dict, description="Count of occurrences per risk type")

