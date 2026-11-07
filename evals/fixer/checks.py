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


def check_bug_03(source: str) -> List[str]:
    """BUG-03: a 422 instrument decline must not be recorded as a successful capture."""
    code = _strip_comments(source)
    branch = re.search(
        r"if\s*\(\s*statusCode\s*===\s*422\b[\s\S]*?(?=if\s*\(\s*statusCode\s*===\s*504\b)",
        code,
    )
    if not branch:
        return ["the 422 decline branch was not found"]

    body = branch.group(0)
    problems = []
    if "shopState.recordCaptureSuccess" in body:
        problems.append("the decline branch records a capture")
    if not re.search(r"\bsuccess\s*:\s*false\b", body):
        problems.append("the decline branch reports success")
    if not re.search(r"\bstatus\s*:\s*['\"]FAILED['\"]", body):
        problems.append("the decline branch does not return a failed status")
    if not re.search(r"\berror\s*:\s*['\"][^'\"]*INSTRUMENT_DECLINED", body):
        problems.append("the decline branch does not surface INSTRUMENT_DECLINED")
    return problems


def check_bug_09(source: str) -> List[str]:
    """BUG-09: a previously processed webhook ID must short-circuit before side effects."""
    code = _strip_comments(source)
    guard = re.search(
        r"if\s*\(\s*shopState\.hasWebhookEvent\s*\(\s*event\.id\s*\)\s*\)\s*\{",
        code,
    )
    if not guard:
        return ["the webhook deduplication guard was not found"]

    body_start = guard.end()
    return_at = code.find("return;", body_start)
    if return_at < 0:
        return ["the webhook deduplication guard does not return"]

    duplicate_reply = code[body_start:return_at]
    problems = []
    if "DUPLICATE_IGNORED" not in duplicate_reply:
        problems.append("the duplicate webhook is not acknowledged as ignored")
    if "verifyWebhookSignature" not in code[:guard.start()]:
        problems.append("webhook deduplication runs before signature verification")

    guard_end = return_at + len("return;")
    for operation in ("shopState.recordWebhookEvent", "shopState.recordCaptureSuccess"):
        operation_at = code.find(operation)
        if operation_at >= 0 and operation_at < guard_end:
            problems.append("the webhook deduplication guard does not precede side effects")
            break
    return problems


CHECKS: Dict[str, Callable[[str], List[str]]] = {
    "BUG-01": check_bug_01,
    "BUG-03": check_bug_03,
    "BUG-09": check_bug_09,
}


def check_patched(bug_id: str, source: str) -> List[str]:
    """Problems found in the patched source. Raises KeyError if no check exists for this bug yet."""
    return CHECKS[bug_id](source)
