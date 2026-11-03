"""Behaviour checks: a diff that applies but does not fix the bug must be caught."""

from pathlib import Path

import pytest

from ai.fixer import apply_to_copy
from evals.fixer.checks import check_patched

ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "targets" / "demo-shop"
GOOD_DIFF = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-01.diff").read_text(encoding="utf-8")
ID_EXPRESSION = "crypto.createHash('sha256').update(`capture-${orderId}`).digest('hex')"


@pytest.fixture
def patched(tmp_path):
    return (apply_to_copy(GOOD_DIFF, SHOP, tmp_path / "p") / "src" / "checkout.ts").read_text(encoding="utf-8")


def test_the_curated_fix_passes(patched):
    assert check_patched("BUG-01", patched) == []


def test_the_unfixed_shop_fails():
    original = (SHOP / "src" / "checkout.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-01", original) == ["captureOrder is still called without paypalRequestId"]


def test_a_random_request_id_fails(patched):
    problems = check_patched("BUG-01", patched.replace(ID_EXPRESSION, "crypto.randomUUID()"))
    assert any("random or time-based" in p for p in problems)


def test_a_request_id_not_tied_to_the_order_fails(patched):
    problems = check_patched("BUG-01", patched.replace(ID_EXPRESSION, "'static-key'"))
    assert problems == ["the request id is not derived from the order id"]


def test_a_commented_out_request_id_does_not_count(patched):
    assert check_patched("BUG-01", patched.replace("        paypalRequestId,\n", "        // paypalRequestId,\n"))


def test_a_differently_named_variable_is_followed(patched):
    renamed = patched.replace("const paypalRequestId =", "const key =").replace("        paypalRequestId,\n", "        paypalRequestId: key,\n")
    assert check_patched("BUG-01", renamed) == []


def test_bugs_without_a_check_are_reported_as_such(patched):
    with pytest.raises(KeyError):
        check_patched("BUG-02", patched)
