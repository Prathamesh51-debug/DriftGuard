"""Behaviour checks for a patched file: does the fix do what the bug's safe behaviour demands?

These are static checks on the patched source. They catch a diff that applies but does nothing
useful, which line overlap with a reference cannot. The real proof stays the chaos re-run going green.
"""

import re
from typing import Callable, Dict, List

RANDOM = re.compile(r"randomUUID|Math\.random|Date\.now|new Date|uuid|randomBytes|performance\.now", re.I)


def _strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)


def check_bug_01(source: str) -> List[str]:
    """BUG-01: captureOrder must send a PayPal-Request-Id that is the same on every retry of an order."""
    code = _strip_comments(source)
    call = re.search(r"captureOrder\(\s*\{(.*?)\}\s*\)", code, re.S)
    if not call:
        return ["the captureOrder call was not found"]
    field = re.search(r"\bpaypalRequestId\b(?:\s*:\s*([^,\n}]+))?", call.group(1))
    if not field:
        return ["captureOrder is still called without paypalRequestId"]

    expression = (field.group(1) or "paypalRequestId").strip()
    if re.fullmatch(r"[A-Za-z_$][\w$]*", expression):  # a variable: look at how it is defined
        assignment = re.search(rf"\b(?:const|let|var)\s+{re.escape(expression)}\s*=\s*([^;]+);", code, re.S)
        if not assignment:
            return [f"the value of {expression} is not defined in the file"]
        expression = assignment.group(1)

    problems = []
    if RANDOM.search(expression):
        problems.append("the request id is random or time-based, so a retry would send a different one")
    if "orderId" not in expression:
        problems.append("the request id is not derived from the order id")
    return problems


CHECKS: Dict[str, Callable[[str], List[str]]] = {"BUG-01": check_bug_01}


def check_patched(bug_id: str, source: str) -> List[str]:
    """Problems found in the patched source. Raises KeyError if no check exists for this bug yet."""
    return CHECKS[bug_id](source)
