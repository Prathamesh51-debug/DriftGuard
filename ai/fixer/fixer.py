"""
Fixer: turns a failing Result into a diff for the target app.

Planner Ref: Part 9 (Role C, C5). AI proposes, code decides: the model only drafts
a diff. Code rejects it unless it touches the one allowed file, stays small and
applies cleanly to a copy of the app. It never edits the original. The verdict
that the fix works still comes from re-running the chaos scenario.
"""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

from contracts import Result, Scenario, Verdict

from .bugs import BugEntry
from .llm import LLMClient, LLMError, extract_json
from .patcher import check_diff, normalize_diff
from .prompt import SYSTEM_PROMPT, build_user_prompt

MAX_ATTEMPTS = 3


class FixProposal(BaseModel):
    bug_id: str
    applies: bool
    source: str  # "llm" or "known_fix"
    provider: Optional[str] = None  # which model answered, when source is "llm"
    diff: Optional[str] = None
    explanation: Optional[str] = None
    files: List[str] = []
    lines_changed: int = 0
    attempts: int
    error: Optional[str] = None


def _parse_reply(raw: str) -> dict:
    data = extract_json(raw)
    if not isinstance(data.get("diff"), str) or not data["diff"].strip():
        raise ValueError('reply must be a JSON object with a non-empty "diff" string')
    return data


def propose_fix(
    result: Result,
    scenario: Scenario,
    bug: BugEntry,
    shop_dir: Path,
    llm: LLMClient,
    *,
    known_fix: Optional[Path] = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> FixProposal:
    """Ask the model for a fix, up to `max_attempts` times, feeding each rejection back to it.

    If every attempt is rejected and `known_fix` is given, fall back to that patch (if it applies).
    """
    if result.verdict != Verdict.FAIL:
        raise ValueError(f"nothing to fix: verdict is {result.verdict.value}")

    shop_dir = Path(shop_dir)
    source = (shop_dir / bug.file).read_text(encoding="utf-8")
    error: Optional[str] = None

    for attempt in range(1, max_attempts + 1):
        try:
            raw = llm.complete(SYSTEM_PROMPT, build_user_prompt(result, scenario, bug, source, error))
        except LLMError as exc:  # every provider is down: skip straight to the curated patch
            error = f"No model available: {exc}"
            break
        try:
            reply = _parse_reply(raw)
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            error = f"Reply was not usable: {exc}"
            continue
        diff = normalize_diff(reply["diff"])
        check = check_diff(diff, shop_dir, allowed_file=bug.file)
        if check.ok:
            return FixProposal(
                bug_id=bug.id, applies=True, source="llm", provider=getattr(llm, "last_provider", None), diff=diff,
                explanation=reply.get("explanation"), files=check.files,
                lines_changed=check.lines_changed, attempts=attempt,
            )
        error = f"The diff was rejected: {check.error}"

    if known_fix is not None and Path(known_fix).is_file():
        diff = normalize_diff(Path(known_fix).read_text(encoding="utf-8"))
        check = check_diff(diff, shop_dir, allowed_file=bug.file)
        if check.ok:
            return FixProposal(
                bug_id=bug.id, applies=True, source="known_fix", diff=diff,
                explanation="Model attempts failed; used the curated patch.",
                files=check.files, lines_changed=check.lines_changed, attempts=max_attempts,
            )
        error = f"{error} Known fix also failed: {check.error}"

    return FixProposal(bug_id=bug.id, applies=False, source="llm", attempts=max_attempts, error=error)
