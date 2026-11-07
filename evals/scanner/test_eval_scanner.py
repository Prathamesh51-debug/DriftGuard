"""
Tests for Scanner Evaluation Suite (evals/scanner).
"""

from pathlib import Path
import pytest

from evals.scanner import (
    EvaluationMetrics,
    evaluate_demo_shop,
    evaluate_real_repos,
    format_eval_report,
)


DEMO_SHOP_SRC = Path(__file__).resolve().parents[2] / "targets" / "demo-shop" / "src"


def test_evaluate_demo_shop_precision_and_recall():
    metrics = evaluate_demo_shop(DEMO_SHOP_SRC)

    assert isinstance(metrics, EvaluationMetrics)
    assert metrics.total_ground_truth == 8
    assert metrics.true_positives == 8
    assert metrics.false_negatives == 0
    assert metrics.recall == 1.0
    assert metrics.precision >= 0.8
    assert metrics.f1_score >= 0.85


def test_evaluate_real_repos(tmp_path):
    res = evaluate_real_repos(tmp_path)

    assert res["total_samples"] == 5
    assert res["accuracy"] >= 0.8
    assert res["recall"] >= 0.8


def test_format_eval_report(tmp_path):
    metrics = evaluate_demo_shop(DEMO_SHOP_SRC)
    real_res = evaluate_real_repos(tmp_path)
    report = format_eval_report(metrics, real_res)

    assert "# DriftGuard Code Scanner Evaluation Report" in report
    assert "100.0%" in report  # 100% recall
    assert "BUG-01" in report
    assert "BUG-10" in report
    assert "Devpost" in report

