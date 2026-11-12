"""Fixer tests: the model's diff is accepted only when code can prove it is safe to use."""

import json
from pathlib import Path

import pytest

from ai.fixer import ScriptedLLM, apply_to_copy, check_diff, find_bug, load_bugs, normalize_diff, propose_fix
from contracts import Result, Scenario

ROOT = Path(__file__).resolve().parents[3]
SHOP = ROOT / "targets" / "demo-shop"
FIXTURES = ROOT / "contracts" / "fixtures"
KNOWN_FIX = ROOT / "ai" / "fixer" / "known_fixes" / "BUG-01.diff"
GOOD_DIFF = KNOWN_FIX.read_text(encoding="utf-8")


@pytest.fixture
def scenario():
    return Scenario.model_validate_json((FIXTURES / "f1_scenario.json").read_text(encoding="utf-8"))


@pytest.fixture
def failing():
    return Result.model_validate_json((FIXTURES / "f1_result_fail.json").read_text(encoding="utf-8"))


@pytest.fixture
def bug(scenario):
    return find_bug(scenario, load_bugs())


def reply(diff: str, explanation: str = "Sends a stable PayPal-Request-Id.") -> str:
    return json.dumps({"diff": diff, "explanation": explanation})


def test_f1_scenario_maps_to_bug_01(bug):
    assert bug.id == "BUG-01"
    assert bug.file == "src/checkout.ts"


def test_all_curated_patches_apply_to_the_current_shop():
    for patch in sorted((ROOT / "ai" / "fixer" / "known_fixes").glob("BUG-*.diff")):
        number = int(patch.stem.split("-")[1])
        target = "src/checkout.ts" if number <= 7 else ("src/webhooks.ts" if number <= 9 else "src/assistant.ts")
        checked = check_diff(patch.read_text(encoding="utf-8"), SHOP, target)
        assert checked.ok, f"{patch.name} no longer applies: {checked.error}"


def test_good_diff_is_accepted_and_applies_to_a_copy_only(failing, scenario, bug, tmp_path):
    original = (SHOP / bug.file).read_text(encoding="utf-8")
    proposal = propose_fix(failing, scenario, bug, SHOP, ScriptedLLM([reply(GOOD_DIFF)]))

    assert proposal.applies and proposal.source == "llm" and proposal.attempts == 1
    assert proposal.files == ["src/checkout.ts"]
    assert proposal.lines_changed > 3

    patched = apply_to_copy(proposal.diff, SHOP, tmp_path / "patched")
    assert "paypalRequestId," in (patched / bug.file).read_text(encoding="utf-8")
    assert "ordersController.getOrder" in (patched / bug.file).read_text(encoding="utf-8")
    assert (SHOP / bug.file).read_text(encoding="utf-8") == original


def test_repo_root_paths_are_normalised(failing, scenario, bug):
    prefixed = GOOD_DIFF.replace("a/src", "a/targets/demo-shop/src").replace("b/src", "b/targets/demo-shop/src")
    assert "targets/demo-shop" not in normalize_diff(prefixed)
    proposal = propose_fix(failing, scenario, bug, SHOP, ScriptedLLM([reply(prefixed)]))
    assert proposal.applies


def test_fenced_reply_is_accepted(failing, scenario, bug):
    fenced = "```json\n" + reply(GOOD_DIFF) + "\n```"
    assert propose_fix(failing, scenario, bug, SHOP, ScriptedLLM([fenced])).applies


def test_normalize_diff_handles_crlf_and_code_fences():
    crlf_diff = "```diff\r\n--- a/targets/demo-shop/src/checkout.ts\r\n+++ b/targets/demo-shop/src/checkout.ts\r\n@@ -1,1 +1,1 @@\r\n-old\r\n+new\r\n```\r\n"
    normalized = normalize_diff(crlf_diff)
    assert "\r" not in normalized
    assert "```" not in normalized
    assert "--- a/src/checkout.ts\n+++ b/src/checkout.ts\n" in normalized



def test_diff_touching_another_file_is_rejected_then_retried(failing, scenario, bug):
    wrong_file = GOOD_DIFF.replace("src/checkout.ts", "src/server.ts")
    llm = ScriptedLLM([reply(wrong_file), reply(GOOD_DIFF)])
    proposal = propose_fix(failing, scenario, bug, SHOP, llm)

    assert proposal.applies and proposal.attempts == 2
    assert "may only change src/checkout.ts" in llm.calls[1]["user"]  # rejection is fed back to the model


def test_bad_json_is_retried(failing, scenario, bug):
    llm = ScriptedLLM(["Sure! Here is a fix...", reply(GOOD_DIFF)])
    proposal = propose_fix(failing, scenario, bug, SHOP, llm)
    assert proposal.applies and proposal.attempts == 2
    assert "not usable" in llm.calls[1]["user"]


def test_diff_that_does_not_apply_is_rejected(failing, scenario, bug):
    stale = GOOD_DIFF.replace("import { shopState } from './state';", "import { somethingElse } from './x';")
    proposal = propose_fix(failing, scenario, bug, SHOP, ScriptedLLM([reply(stale)] * 3), known_fixes=[])
    assert not proposal.applies and "rejected" in proposal.error


def test_oversized_diff_is_rejected():
    check = check_diff(GOOD_DIFF, SHOP, "src/checkout.ts", max_changed_lines=2)
    assert not check.ok and "limit is 2" in check.error


def test_falls_back_to_known_fix_after_three_failures(failing, scenario, bug):
    llm = ScriptedLLM(["nope", "still nope", "no"])
    proposal = propose_fix(failing, scenario, bug, SHOP, llm, known_fixes=[KNOWN_FIX])
    assert proposal.applies and proposal.source == "known_fix" and len(llm.calls) == 3


def test_offline_curated_fix_does_not_claim_failed_model_attempts(failing, scenario, bug):
    from ai.fixer.providers import OfflineLLM

    proposal = propose_fix(failing, scenario, bug, SHOP, OfflineLLM(), known_fixes=[KNOWN_FIX])
    assert proposal.applies and proposal.source == "known_fix"
    assert proposal.attempts == 0
    assert "without a model call" in proposal.explanation


def test_gives_up_cleanly_when_nothing_applies(failing, scenario, bug):
    proposal = propose_fix(failing, scenario, bug, SHOP, ScriptedLLM(["nope"] * 3), known_fixes=[])
    assert not proposal.applies and proposal.diff is None and proposal.attempts == 3


def test_passing_result_has_nothing_to_fix(scenario, bug):
    passing = Result.model_validate_json((FIXTURES / "f1_result_pass.json").read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="nothing to fix"):
        propose_fix(passing, scenario, bug, SHOP, ScriptedLLM([]))


def test_default_fallback_skips_a_broken_curated_patch_and_uses_the_next(failing, scenario, bug, tmp_path, monkeypatch):
    from ai.fixer import bugs

    team, bundled = tmp_path / "team", tmp_path / "bundled"
    team.mkdir(), bundled.mkdir()
    (team / "BUG-01.patch").write_text("--- a/src/checkout.ts\n+++ b/src/checkout.ts\n@@ -1,3 +1,4 @@\n not the real context\n+x\n", encoding="utf-8")
    (bundled / "BUG-01.diff").write_text(GOOD_DIFF, encoding="utf-8")
    monkeypatch.setattr(bugs, "KNOWN_FIX_DIRS", [team, bundled])

    proposal = propose_fix(failing, scenario, bug, SHOP, ScriptedLLM(["nope"] * 3))  # known_fixes left at its default
    assert proposal.applies and proposal.source == "known_fix"
    assert "BUG-01.diff" in proposal.explanation


def test_the_teams_curated_patch_is_preferred_once_it_applies(failing, scenario, bug, tmp_path, monkeypatch):
    from ai.fixer import bugs

    team, bundled = tmp_path / "team", tmp_path / "bundled"
    team.mkdir(), bundled.mkdir()
    (team / "BUG-01.patch").write_text(GOOD_DIFF, encoding="utf-8")
    (bundled / "BUG-01.diff").write_text(GOOD_DIFF, encoding="utf-8")
    monkeypatch.setattr(bugs, "KNOWN_FIX_DIRS", [team, bundled])

    proposal = propose_fix(failing, scenario, bug, SHOP, ScriptedLLM(["nope"] * 3))
    assert "BUG-01.patch" in proposal.explanation


def test_a_bundled_curated_fix_exists_for_bug_01():
    from ai.fixer import known_fix_candidates

    assert any(p.name == "BUG-01.diff" for p in known_fix_candidates("BUG-01"))


def test_verified_role_c_bug_01_patch_is_the_first_fallback_candidate():
    from ai.fixer import known_fix_candidates

    assert known_fix_candidates("BUG-01")[0] == KNOWN_FIX


def test_verified_role_c_bug_02_patch_is_the_first_fallback_candidate():
    from ai.fixer import known_fix_candidates

    expected = ROOT / "ai" / "fixer" / "known_fixes" / "BUG-02.diff"
    assert known_fix_candidates("BUG-02")[0] == expected


def test_verified_role_c_bug_04_patch_is_the_first_fallback_candidate():
    from ai.fixer import known_fix_candidates

    expected = ROOT / "ai" / "fixer" / "known_fixes" / "BUG-04.diff"
    assert known_fix_candidates("BUG-04")[0] == expected


def test_role_c_bug_09_patch_is_the_first_fallback_candidate():
    from ai.fixer import known_fix_candidates

    expected = ROOT / "ai" / "fixer" / "known_fixes" / "BUG-09.diff"
    assert known_fix_candidates("BUG-09")[0] == expected


def test_the_app_record_is_in_the_fixer_prompt(failing, scenario, bug):
    from ai.fixer.prompt import build_user_prompt

    prompt = build_user_prompt(failing, scenario, bug, "source")
    assert "The app's own records show 0 capture(s)." in prompt
    assert "ordersController.getOrder" in prompt


def test_bug_01_sdk_guidance_checks_paypal_state_after_timeout():
    from ai.fixer.prompt import SDK_NOTES

    notes = SDK_NOTES["F1_LOST_CAPTURE_RESPONSE"]
    assert "ordersController.getOrder({ id: orderId })" in notes
    assert "COMPLETED capture" in notes


def test_bug_09_guidance_prevents_duplicate_effects_across_checkout_and_webhook():
    from ai.fixer.prompt import SDK_NOTES

    notes = SDK_NOTES["F6_WEBHOOK_REPLAY"]
    assert "shopState.hasWebhookEvent(event.id)" in notes
    assert "captureCount" in notes


def test_safe_link_falls_back_to_copy2_on_os_error(tmp_path, monkeypatch):
    import os
    from ai.fixer.verify_run import _safe_link

    src = tmp_path / "source.txt"
    dst = tmp_path / "dest.txt"
    src.write_text("driftguard-payload", encoding="utf-8")

    def failing_link(_s, _d):
        raise OSError(17, "Cross-device link or WinError 17")

    monkeypatch.setattr(os, "link", failing_link)
    _safe_link(str(src), str(dst))
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "driftguard-payload"


