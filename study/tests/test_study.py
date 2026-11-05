"""Tests for the 25-repo public study."""

import json
from pathlib import Path
import pytest

from study.scanner_eval import compute_metrics, format_report_markdown, load_study_data


def test_study_dataset_integrity():
    data = load_study_data()
    assert len(data) == 25, f"Expected exactly 25 repos, got {len(data)}"

    ids = [r["id"] for r in data]
    assert len(set(ids)) == 25
    expected_ids = [f"repo-{i:02d}" for i in range(1, 26)]
    assert ids == expected_ids

    for r in data:
        assert "name" in r
        assert "stack" in r
        assert "paypal_integration" in r
        assert isinstance(r["api_calls_found"], int)
        assert isinstance(r["static_risk_detected"], bool)
        assert isinstance(r["risk_types"], list)
        assert "notes" in r


def test_study_metrics_calculation():
    data = load_study_data()
    metrics = compute_metrics(data)

    assert metrics["total_repos"] == 25
    assert metrics["static_risk_count"] == 18
    assert metrics["static_risk_pct"] == 72.0
    assert metrics["clean_count"] == 7
    assert metrics["clean_pct"] == 28.0
    assert metrics["tier2_eligible"] == 7
    assert metrics["tier2_reproduced"] == 5
    assert metrics["tier2_reproduced_pct"] == 71.4

    breakdown = metrics["risk_type_breakdown"]
    assert breakdown["MISSING_IDEMPOTENCY_KEY"] == 13
    assert breakdown["BLIND_RETRY_TIMEOUT"] == 5
    assert breakdown["UNVERIFIED_WEBHOOK"] == 4
    assert breakdown["FLOAT_ROUNDING"] == 4


def test_format_report_markdown():
    data = load_study_data()
    metrics = compute_metrics(data)
    md = format_report_markdown(metrics)

    assert "# DriftGuard Public Repo Study" in md
    assert "18 of 25" in md
    assert "72.0%" in md
    assert "5 of 7 eligible apps (71.4%)" in md
