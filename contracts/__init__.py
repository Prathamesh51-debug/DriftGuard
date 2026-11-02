"""
DriftGuard Contracts Package.
Provides canonical Scenario and Result schemas, validation helpers, and enums.
"""

from .models import (
    ApprovalResult,
    Evidence,
    Expectation,
    FaultType,
    InjectAction,
    ObservedState,
    Result,
    Scenario,
    TargetCall,
    Verdict,
)

__all__ = [
    "ApprovalResult",
    "FaultType",
    "Verdict",
    "TargetCall",
    "InjectAction",
    "Expectation",
    "Scenario",
    "ObservedState",
    "Evidence",
    "Result",
]

