"""Code check for Explainer text: every number and ID it mentions must exist in the Result.

The model writes the words; this decides whether they can be shown. Limits: it checks digits and
PayPal-style IDs, not number words ("twice") or claims that use no figures.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Set

from contracts import Result, Scenario

NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\w)")
PAYPAL_ID = re.compile(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{12,}\b")
PROXY_REF = re.compile(r"\breq_[0-9a-z]+\b")


def _decimal(token: str):
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def known_ids(result: Result, scenario: Scenario) -> Set[str]:
    ev = result.evidence
    ids = [
        *ev.paypal_order_ids, *ev.paypal_capture_ids, *ev.paypal_refund_ids,
        *ev.proxy_log_refs, *ev.webhook_event_ids, result.scenario_id, scenario.scenario_id,
    ]
    return {i for i in ids if i}


def known_numbers(result: Result, scenario: Scenario) -> Set[Decimal]:
    obs, expect = result.observed, scenario.expect
    raw = [obs.captures, obs.amount_captured, obs.orders_created, obs.refunds_issued,
           expect.captures_per_purchase, expect.amount]
    numbers = {d for d in (_decimal(str(v)) for v in raw if v is not None) if d is not None}
    for text in (result.money_impact, result.rule, result.error_message or ""):
        numbers |= {Decimal(n) for n in NUMBER.findall(text)}
    captured, wanted = _decimal(obs.amount_captured), _decimal(expect.amount or "")
    if captured is not None and wanted is not None:
        numbers.add(abs(captured - wanted))
    return numbers


def verify_text(texts: Iterable[str], result: Result, scenario: Scenario) -> List[str]:
    """Return a list of problems; empty means every figure and ID in the text is backed by the Result."""
    text = "\n".join(texts)
    ids = known_ids(result, scenario)
    for known in sorted(ids, key=len, reverse=True):  # remove known IDs so their digits are not read as numbers
        text = text.replace(known, " ")

    problems = []
    invented = sorted(set(PAYPAL_ID.findall(text)) | set(PROXY_REF.findall(text)))
    problems += [f"ID {i} is not in the result" for i in invented]
    for token in invented:
        text = text.replace(token, " ")

    allowed = known_numbers(result, scenario)
    seen = set()
    for token in NUMBER.findall(text):
        value = Decimal(token)
        if value not in allowed and token not in seen:
            seen.add(token)
            problems.append(f"number {token} is not in the result")
    return problems
