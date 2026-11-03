"""Eval runner tests, using scripted replies so nothing touches the network."""

import json
from pathlib import Path

from ai.fixer import ScriptedLLM
from evals.fixer.run_eval import evaluate, to_markdown

ROOT = Path(__file__).resolve().parents[2]
GOOD_DIFF = (ROOT / "ai" / "fixer" / "known_fixes" / "BUG-01.diff").read_text(encoding="utf-8")


def good_reply():
    return json.dumps({"diff": GOOD_DIFF, "explanation": "stable request id"})


def comment_only_reply():
    """A diff that applies cleanly but only adds a comment, so it does not fix the bug."""
    lines = (ROOT / "targets" / "demo-shop" / "src" / "checkout.ts").read_text(encoding="utf-8").splitlines()
    context = lambda chunk: "".join(f" {line}\n" for line in chunk)  # noqa: E731
    diff = ("--- a/src/checkout.ts\n+++ b/src/checkout.ts\n@@ -80,4 +80,5 @@\n"
            + context(lines[79:81]) + "+  // TODO\n" + context(lines[81:83]))
    return json.dumps({"diff": diff, "explanation": "x"})


def test_counts_correct_fixes_and_failures():
    replies = {1: [good_reply()], 2: ["nope"] * 3, 3: [good_reply()]}
    summary = evaluate("BUG-01", 3, lambda i: ScriptedLLM(replies[i]))
    assert (summary["applies"], summary["first_try"], summary["correct"]) == (2, 2, 2)
    assert summary["rows"][1]["applies"] is False


def test_a_diff_that_applies_but_does_not_fix_is_not_counted_correct():
    summary = evaluate("BUG-01", 1, lambda i: ScriptedLLM([comment_only_reply()]))
    assert summary["applies"] == 1 and summary["correct"] == 0
    assert "captureOrder is still called without paypalRequestId" in summary["rows"][0]["problems"]


def test_the_curated_fallback_is_off_so_the_model_is_measured_alone():
    summary = evaluate("BUG-01", 1, lambda i: ScriptedLLM(["nope"] * 3))
    assert summary["applies"] == 0  # would be 1 if the bundled curated fix were used


def test_markdown_table_lists_the_numbers_and_failures():
    summary = evaluate("BUG-01", 2, lambda i: ScriptedLLM([good_reply()] if i == 1 else ["nope"] * 3))
    table = to_markdown(summary, "scripted")
    assert "| 2 | 1/2 | 1/2 | 1/2 |" in table and "run 2" in table


def test_ablation_removes_the_sdk_notes_and_restores_them():
    from ai.fixer import fixer as fixer_module
    from ai.fixer import prompt
    from evals.fixer.run_eval import without_sdk_notes

    before = (dict(prompt.SDK_NOTES), fixer_module.SYSTEM_PROMPT)
    with without_sdk_notes():
        assert prompt.SDK_NOTES == {}
        assert "listed under SDK notes" not in fixer_module.SYSTEM_PROMPT
    assert (prompt.SDK_NOTES, fixer_module.SYSTEM_PROMPT) == before


def test_blind_copy_drops_hint_comments_and_keeps_the_code(tmp_path):
    from evals.fixer.run_eval import SHOP, blind_copy

    original = (SHOP / "src" / "checkout.ts").read_text(encoding="utf-8")
    out = blind_copy(SHOP, tmp_path / "shop")
    blind = (out / "src" / "checkout.ts").read_text(encoding="utf-8")
    assert "BUG-01" in original and "BUG-01" not in blind
    assert "ordersController.captureOrder(" in blind  # the code itself is untouched
    assert (SHOP / "src" / "checkout.ts").read_text(encoding="utf-8") == original  # the real shop is not modified
