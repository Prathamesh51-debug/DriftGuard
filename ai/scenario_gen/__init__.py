"""
DriftGuard Scenario Generator Package
Provides deterministic scenario generation and LLM-assisted scenario attack proposals.
Planner Ref: Role B (AI + Attacks), Day 8 (Phase 2 Breadth).
"""

from .generator import (
    ScenarioGenerator,
    calculate_expectation,
    export_scenario_fixtures,
    FAULT_TEMPLATES,
)

__all__ = [
    "ScenarioGenerator",
    "calculate_expectation",
    "export_scenario_fixtures",
    "FAULT_TEMPLATES",
]

