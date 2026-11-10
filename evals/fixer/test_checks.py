"""Behaviour checks: a diff that applies but does not fix the bug must be caught."""

from pathlib import Path

import pytest

from ai.fixer import apply_to_copy
from ai.fixer.bugs import known_fix_candidates
from ai.fixer.patcher import normalize_diff
from evals.fixer.checks import CHECKS, check_patched

ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "targets" / "demo-shop"
GOOD_DIFF = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-01.diff").read_text(encoding="utf-8")
GOOD_DIFF_02 = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-02.diff").read_text(encoding="utf-8")
GOOD_DIFF_03 = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-03.diff").read_text(encoding="utf-8")
GOOD_DIFF_04 = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-04.diff").read_text(encoding="utf-8")
GOOD_DIFF_09 = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-09.diff").read_text(encoding="utf-8")
GOOD_DIFF_10 = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-10.diff").read_text(encoding="utf-8")
ID_EXPRESSION = "createHash('sha256').update(`capture-${orderId}`).digest('hex')"

SAFE_F2_SOURCE = """
import { randomUUID } from 'crypto';
export async function createCheckoutOrder() {
  const paypalRequestId = randomUUID();
  const referenceId = `cart-${Date.now()}`;
  const invoiceId = `INV-${Math.random()}`;
  let attempts = 0;
  while (attempts <= 1) {
    attempts += 1;
    await ordersController.createOrder({ body: { purchaseUnits: [{ referenceId, invoiceId }] }, prefer: 'return=representation', paypalRequestId });
  }
}
"""


def _bug_02_problems(source):
    checker = CHECKS.get("BUG-02")
    return checker(source) if checker else ["BUG-02 behavioral check is missing"]


def test_bug_02_original_create_order_fails_without_request_id():
    original = (SHOP / "src" / "checkout.ts").read_text(encoding="utf-8")
    assert _bug_02_problems(original) == ["createOrder is still called without paypalRequestId"]


def test_bug_02_rejects_an_amount_only_idempotency_key():
    unsafe = SAFE_F2_SOURCE.replace("randomUUID()", "createHash('sha256').update(`create-${amount}`).digest('hex')")
    assert any("request ID must be unique per purchase" in p for p in _bug_02_problems(unsafe))


def test_bug_02_bundled_patch_reuses_stable_request_fields(tmp_path):
    patched = (apply_to_copy(GOOD_DIFF_02, SHOP, tmp_path / "bug02-bundled") / "src" / "checkout.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-02", patched) == []


def test_bug_02_accepts_one_unique_request_id_and_body_for_all_retries():
    assert _bug_02_problems(SAFE_F2_SOURCE) == []


def test_bug_02_rejects_literal_key_even_when_safe_variable_exists():
    unsafe = SAFE_F2_SOURCE.replace("prefer: 'return=representation', paypalRequestId", "prefer: 'return=representation', paypalRequestId: 'shared'")
    assert _bug_02_problems(unsafe)


def test_bug_02_rejects_request_id_replaced_by_function_call():
    unsafe = SAFE_F2_SOURCE.replace("prefer: 'return=representation', paypalRequestId", "prefer: 'return=representation', paypalRequestId: randomUUID()")
    assert _bug_02_problems(unsafe)


def test_bug_02_rejects_request_id_generated_inside_retry_loop():
    unsafe = SAFE_F2_SOURCE.replace("  const paypalRequestId = randomUUID();\n", "")
    unsafe = unsafe.replace("  while (attempts <= 1) {\n", "  while (attempts <= 1) {\n    const paypalRequestId = randomUUID();\n")
    assert any("created once before the retry loop" in p for p in _bug_02_problems(unsafe))


def test_bug_02_rejects_reference_and_invoice_ids_regenerated_inside_retry_loop():
    unsafe = SAFE_F2_SOURCE.replace("  const referenceId = `cart-${Date.now()}`;\n", "")
    unsafe = unsafe.replace("  const invoiceId = `INV-${Math.random()}`;\n", "")
    unsafe = unsafe.replace("[{ referenceId, invoiceId }]", "[{ referenceId: `cart-${Date.now()}`, invoiceId: `INV-${Math.random()}` }]")
    assert any("same order body on every retry" in p for p in _bug_02_problems(unsafe))


def test_bug_04_original_random_invoice_is_rejected():
    original = (SHOP / "src/checkout.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-04", original)


def test_bug_04_reference_fix_has_stable_distinct_cart_identity(tmp_path):
    patched = (apply_to_copy(GOOD_DIFF_04, SHOP, tmp_path / "bug04") / "src/checkout.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-04", patched) == []


def test_bug_04_accepts_reference_variable_derived_from_cart(tmp_path):
    patched = (apply_to_copy(GOOD_DIFF_04, SHOP, tmp_path / "bug04-reference-var") / "src/checkout.ts").read_text(encoding="utf-8")
    patched = patched.replace("  const invoiceId =", "  const referenceId = `cart-${cartId}`;\n  const invoiceId =")
    patched = patched.replace("referenceId: cartId,", "referenceId,")
    assert check_patched("BUG-04", patched) == []


def test_bug_04_rejects_timestamp_or_amount_only_identity(tmp_path):
    patched = (apply_to_copy(GOOD_DIFF_04, SHOP, tmp_path / "bug04-unsafe") / "src/checkout.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-04", patched.replace("crypto.randomUUID()", "Date.now()"))
    assert check_patched("BUG-04", patched.replace("`${cartId}:${finalAmount}`", "`${finalAmount}`"))


@pytest.fixture
def patched(tmp_path):
    return (apply_to_copy(GOOD_DIFF, SHOP, tmp_path / "p") / "src" / "checkout.ts").read_text(encoding="utf-8")


def test_the_curated_fix_passes(patched):
    assert check_patched("BUG-01", patched) == []


def test_the_curated_fix_checks_paypal_order_state_before_retry(patched):
    assert "ordersController.getOrder" in patched
    assert "payments?.captures" in patched


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


def test_idempotency_key_alone_does_not_recover_a_lost_capture_response():
    original = (SHOP / "src" / "checkout.ts").read_text(encoding="utf-8")
    key_only = original.replace(
        "        // BUG-01: Missing paypalRequestId (idempotency key)!\n",
        "        paypalRequestId: `capture-${orderId}`,\n",
    )
    problems = check_patched("BUG-01", key_only)
    assert any("check PayPal order status after an ambiguous capture error" in problem for problem in problems)


def test_a_differently_named_variable_is_followed(patched):
    renamed = patched.replace("const paypalRequestId =", "const key =").replace("        paypalRequestId,\n", "        paypalRequestId: key,\n")
    assert check_patched("BUG-01", renamed) == []


def test_bugs_without_a_check_are_reported_as_such(patched):
    with pytest.raises(KeyError):
        check_patched("BUG-05", patched)


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


def test_bug_03_accepts_removing_false_special_case_when_error_returns_failure():
    original = (SHOP / "src" / "checkout.ts").read_text(encoding="utf-8")
    start = original.index("      const errData =")
    end = original.index("      // On 504", start)
    safe_fallback = original[:start] + original[end:]
    assert check_patched("BUG-03", safe_fallback) == []


def test_bug_09_curated_fix_ignores_replayed_event_before_processing(tmp_path):
    patched_webhooks = (apply_to_copy(GOOD_DIFF_09, SHOP, tmp_path / "bug09") / "src" / "webhooks.ts").read_text(encoding="utf-8")
    assert check_patched("BUG-09", patched_webhooks) == []


def test_bug_09_requires_capture_side_effect_to_be_idempotent_with_checkout(tmp_path):
    patched_webhooks = (apply_to_copy(GOOD_DIFF_09, SHOP, tmp_path / "bug09-order") / "src" / "webhooks.ts").read_text(encoding="utf-8")
    unguarded = patched_webhooks.replace(
        "    if ((shopState.getOrder(orderId)?.captureCount || 0) === 0) {\n"
        "      shopState.recordCaptureSuccess(orderId, captureId, amount);\n"
        "    }",
        "    shopState.recordCaptureSuccess(orderId, captureId, amount);",
    )
    problems = check_patched("BUG-09", unguarded)
    assert any("already recorded by checkout" in problem for problem in problems)


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


def test_bug_09_accepts_a_persistent_set_deduplication_strategy():
    model_style = (SHOP / "src" / "webhooks.ts").read_text(encoding="utf-8")
    model_style = model_style.replace(
        "export async function handleWebhook",
        "const processedEvents = new Set<string>();\n\nexport async function handleWebhook",
    )
    model_style = model_style.replace(
        "  const isDuplicate = false;\n\n  shopState.recordWebhookEvent(event.id, event.event_type, isDuplicate);",
        "  const isDuplicate = processedEvents.has(event.id);\n"
        "  if (isDuplicate) {\n"
        "    res.status(200).json({ status: 'DUPLICATE_IGNORED', eventId: event.id });\n"
        "    return;\n"
        "  }\n"
        "  processedEvents.add(event.id);\n\n"
        "  shopState.recordWebhookEvent(event.id, event.event_type, isDuplicate);",
    )
    model_style = model_style.replace(
        "    shopState.recordCaptureSuccess(orderId, captureId, amount);",
        "    if ((shopState.getOrder(orderId)?.captureCount || 0) === 0) {\n"
        "      shopState.recordCaptureSuccess(orderId, captureId, amount);\n"
        "    }",
    )
    assert check_patched("BUG-09", model_style) == []


def test_bug_10_curated_fix_blocks_buyer_refunds_over_policy_limit(tmp_path):
    patched = apply_to_copy(GOOD_DIFF_10, SHOP, tmp_path / "bug10") / "src" / "assistant.ts"
    assert check_patched("BUG-10", patched.read_text(encoding="utf-8")) == []


def test_bug_10_rejects_a_missing_refund_guard():
    original = (SHOP / "src" / "assistant.ts").read_text(encoding="utf-8")
    assert any("over-limit buyer role guard" in problem for problem in check_patched("BUG-10", original))
