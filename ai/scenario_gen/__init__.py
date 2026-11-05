"""
DriftGuard Scenario Generator Package
Provides deterministic scenario generation and LLM-assisted scenario attack proposals.
Planner Ref: Role B (AI + Attacks), Day 8 (Phase 2 Breadth).
"""

from .generator import (
    ScenarioGenerator,
    calculate_expectation,
    calculate_expected_total,
    export_scenario_fixtures,
    FAULT_TEMPLATES,
    CURRENCY_EXPONENTS,
)

__all__ = [
    "ScenarioGenerator",
    "calculate_expectation",
    "calculate_expected_total",
    "export_scenario_fixtures",
    "FAULT_TEMPLATES",
    "CURRENCY_EXPONENTS",
]

