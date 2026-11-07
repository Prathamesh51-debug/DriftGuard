"""
DriftGuard Scanner Evaluation Suite.
Measures precision and recall against seeded and real-world ground truth.
"""

from .eval_scanner import (
    EvaluationMetrics,
    evaluate_demo_shop,
    evaluate_real_repos,
    format_eval_report,
)
from .ground_truth import REAL_REPOS_BENCHMARK, SEEDED_BENCHMARK

__all__ = [
    "EvaluationMetrics",
    "evaluate_demo_shop",
    "evaluate_real_repos",
    "format_eval_report",
    "REAL_REPOS_BENCHMARK",
    "SEEDED_BENCHMARK",
]

