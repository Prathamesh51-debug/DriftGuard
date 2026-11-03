"""
Explainer: turns a Result into a short plain-English explanation.

Planner Ref: Part 9 (Role C, C4). AI proposes, code decides: the model writes the
words, then code rejects any text that mentions a number or ID not in the Result.
After 3 rejected attempts it falls back to a template built straight from the
Result, so the dashboard always has an explanation that is safe to show.
"""

from typing import List, Optional

from pydantic import BaseModel

from ai.fixer.llm import LLMClient, LLMError, extract_json  # moves to ai/common when the team adapter lands
from contracts import Result, Scenario, Verdict

from .prompt import SYSTEM_PROMPT, build_user_prompt
from .verify import verify_text

MAX_ATTEMPTS = 3
FIELDS = ("headline", "what_happened", "impact")


class Explanation(BaseModel):
    headline: str
    what_happened: str
    impact: str
    source: str  # "llm" or "template"
    provider: Optional[str] = None  # which model answered, when source is "llm"
    attempts: int
    rejected: List[str] = []  # why earlier model attempts were refused


def _parse_reply(raw: str) -> dict:
    data = extract_json(raw)
    if not all(isinstance(data.get(f), str) and data[f].strip() for f in FIELDS):
        raise ValueError(f"reply must be a JSON object with non-empty text for {', '.join(FIELDS)}")
    return data


def template_explanation(result: Result, scenario: Scenario, attempts: int = 0, rejected: Optional[List[str]] = None) -> Explanation:
    """Plain wording built only from the Result's own fields. Passes verify_text by construction."""
    obs, expect = result.observed, scenario.expect
    if result.verdict == Verdict.PASS:
        headline, what = "Test passed", f"PayPal's records match what was expected ({result.rule})."
    elif result.verdict == Verdict.ERROR:
        headline = "Test could not complete"
        what = result.error_message or "The test hit an error before PayPal's records could be checked."
    elif obs.app_recorded_captures is not None and obs.app_recorded_captures != obs.captures:
        headline = "PayPal took the payment but the app has no record of it"
        what = (
            f"PayPal's records show {obs.captures} capture(s) totalling {obs.amount_captured} {expect.currency}, "
            f"but the app's own records show {obs.app_recorded_captures}. Rule broken: {result.rule}."
        )
    else:
        headline = "Payment records do not match"
        what = (
            f"PayPal's records show {obs.captures} capture(s) totalling {obs.amount_captured} {expect.currency}, "
            f"but the test expected {expect.captures_per_purchase} capture(s) of {expect.amount}. "
            f"Rule broken: {result.rule}."
        )
    return Explanation(headline=headline, what_happened=what, impact=result.money_impact,
                       source="template", attempts=attempts, rejected=rejected or [])


def explain(result: Result, scenario: Scenario, llm: LLMClient, *, max_attempts: int = MAX_ATTEMPTS) -> Explanation:
    if result.verdict == Verdict.PASS:  # nothing to explain, so no model call
        return template_explanation(result, scenario)

    rejected: List[str] = []
    feedback: Optional[str] = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw = llm.complete(SYSTEM_PROMPT, build_user_prompt(result, scenario, feedback))
        except LLMError as exc:  # every provider is down: use the template
            rejected.append(f"No model available: {exc}")
            break
        try:
            reply = _parse_reply(raw)
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            problems = [f"reply was not usable: {exc}"]
        else:
            problems = verify_text([reply[f] for f in FIELDS], result, scenario)
            if not problems:
                return Explanation(**{f: reply[f].strip() for f in FIELDS},
                                   source="llm", provider=getattr(llm, "last_provider", None),
                                   attempts=attempt, rejected=rejected)
        feedback = "; ".join(problems)
        rejected.append(feedback)

    return template_explanation(result, scenario, attempts=max_attempts, rejected=rejected)
