"""Behaviour checks: a diff that applies but does not fix the bug must be caught."""

from pathlib import Path

import pytest

from ai.fixer import apply_to_copy
from ai.fixer.bugs import known_fix_candidates
from ai.fixer.patcher import normalize_diff
from evals.fixer.checks import check_patched

ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "targets" / "demo-shop"
GOOD_DIFF = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-01.diff").read_text(encoding="utf-8")
GOOD_DIFF_03 = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-03.diff").read_text(encoding="utf-8")
GOOD_DIFF_09 = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-09.diff").read_text(encoding="utf-8")
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


def test_bug_03_curated_fix_keeps_declined_order_unpaid(tmp_path):
    patched_checkout = (apply_to_copy(GOOD_DIFF_03, SHOP, tmp_path / "bug03") / "src" / "checkout.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-03", patched_checkout) == []


def test_preferred_bug_03_patch_applies_to_current_shop(tmp_path):
    preferred_patch = known_fix_candidates("BUG-03")[0].read_text(encoding="utf-8")
    patched_checkout = (apply_to_copy(normalize_diff(preferred_patch), SHOP, tmp_path / "preferred03") / "src" / "checkout.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-03", patched_checkout) == []


def test_bug_03_original_and_false_success_are_rejected(tmp_path):
    original = (SHOP / "src" / "checkout.ts").read_text(encoding="utf-8")
    problems = check_patched("BUG-03", original)
    assert any("records a capture" in problem for problem in problems)
    assert any("reports success" in problem for problem in problems)

    good_checkout = (apply_to_copy(GOOD_DIFF_03, SHOP, tmp_path / "good03") / "src" / "checkout.ts").read_text(encoding="utf-8")
    bad_checkout = good_checkout.replace("success: false", "success: true")
    assert any("reports success" in problem for problem in check_patched("BUG-03", bad_checkout))


def test_bug_09_curated_fix_ignores_replayed_event_before_processing(tmp_path):
    patched_webhooks = (apply_to_copy(GOOD_DIFF_09, SHOP, tmp_path / "bug09") / "src" / "webhooks.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-09", patched_webhooks) == []


def test_preferred_bug_09_patch_applies_to_current_shop(tmp_path):
    preferred_patch = known_fix_candidates("BUG-09")[0].read_text(encoding="utf-8")
    patched_webhooks = (apply_to_copy(normalize_diff(preferred_patch), SHOP, tmp_path / "preferred09") / "src" / "webhooks.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-09", patched_webhooks) == []


def test_bug_09_original_and_comment_only_guard_are_rejected(tmp_path):
    original = (SHOP / "src" / "webhooks.ts").read_text(encoding="utf-8")
    assert any("deduplication guard" in problem for problem in check_patched("BUG-09", original))

    bad_diff = GOOD_DIFF_09.replace("if (shopState.hasWebhookEvent(event.id)) {", "// if (shopState.hasWebhookEvent(event.id)) {")
    bad_webhooks = (apply_to_copy(bad_diff, SHOP, tmp_path / "bad09") / "src" / "webhooks.ts").read_text(encoding="utf-8")
    assert any("deduplication guard" in problem for problem in check_patched("BUG-09", bad_webhooks))


def test_bug_09_guard_after_event_recording_is_rejected(tmp_path):
    patched_webhooks = (apply_to_copy(GOOD_DIFF_09, SHOP, tmp_path / "reordered09") / "src" / "webhooks.ts").read_text(encoding="utf-8")
    guard_start = patched_webhooks.index("  if (shopState.hasWebhookEvent(event.id)) {")
    guard_end = patched_webhooks.index("\n  const isDuplicate = false;", guard_start)
    guard = patched_webhooks[guard_start:guard_end]
    without_guard = patched_webhooks[:guard_start] + patched_webhooks[guard_end:]
    record_line = "  shopState.recordWebhookEvent(event.id, event.event_type, isDuplicate);"
    record_end = without_guard.index(record_line) + len(record_line)
    bad_order = without_guard[:record_end] + "\n" + guard + without_guard[record_end:]
    assert any("does not precede side effects" in problem for problem in check_patched("BUG-09", bad_order))
