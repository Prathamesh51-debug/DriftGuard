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
    """BUG-01: use a stable request ID and recover a completed capture after an ambiguous timeout."""
    code = _strip_comments(source)
    handler = re.search(r"export\s+async\s+function\s+captureCheckoutOrder\s*\(", code)
    if not handler:
        return ["the capture handler was not found"]
    capture_code = code[handler.start():]
    call = re.search(r"captureOrder\(\s*\{(.*?)\}\s*\)", capture_code, re.S)
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

    timeout = re.search(r"if\s*\(\s*statusCode\s*===\s*504\b[^)]*\)\s*\{", capture_code)
    lookup = re.search(
        r"ordersController\.getOrder\s*\(\s*\{\s*id\s*:\s*orderId\s*\}\s*\)", capture_code
    )
    if not timeout or not lookup or lookup.start() < timeout.end():
        problems.append("does not check PayPal order status after an ambiguous capture error")
    else:
        tail = capture_code[lookup.end():]
        capture = re.search(
            r"const\s+([A-Za-z_$][\w$]*)\s*=\s*[^;\n]*purchaseUnits[^;\n]*\.captures[^;\n]*\.find\s*\(",
            tail,
        )
        if not capture:
            problems.append("does not inspect PayPal's capture list after the status check")
        else:
            capture_name = capture.group(1)
            recovery = tail[capture.end():]
            recovered = re.search(
                rf"if\s*\(\s*{re.escape(capture_name)}\s*\)\s*\{{[\s\S]{{0,800}}?"
                rf"shopState\.recordCaptureSuccess\s*\(\s*orderId\s*,\s*{re.escape(capture_name)}\.id",
                recovery,
            )
            if not recovered:
                problems.append("does not record a confirmed capture before retrying")
    return problems


def check_bug_03(source: str) -> List[str]:
    """BUG-03: a 422 instrument decline must not be recorded as a successful capture."""
    code = _strip_comments(source)
    capture = re.search(r"export\s+async\s+function\s+captureCheckoutOrder\s*\(", code)
    if not capture:
        return ["the capture handler was not found"]
    capture_code = code[capture.start():]
    branch = re.search(
        r"if\s*\(\s*statusCode\s*===\s*422\b[\s\S]*?(?=if\s*\(\s*statusCode\s*===\s*504\b)",
        capture_code,
    )
    if not branch:
        catch = re.search(r"catch\s*\(\s*err\b[^)]*\)\s*\{", capture_code)
        if not catch:
            return ["the capture handler does not catch or propagate decline errors"]
        catch_code = capture_code[catch.start():]
        problems = []
        if "shopState.recordCaptureSuccess" in catch_code:
            problems.append("the capture error path records a capture")
        failure = re.search(
            r"return\s*\{\s*success\s*:\s*false\b[\s\S]*?\bstatus\s*:\s*['\"]FAILED['\"][\s\S]*?\berror\s*:\s*([^,\n}]+)",
            catch_code,
        )
        if not failure:
            problems.append("the decline error path does not return a failed result")
        elif not re.search(r"lastError|INSTRUMENT_DECLINED", failure.group(1)):
            problems.append("the decline error is not surfaced to the caller")
        return problems

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
    """BUG-09: duplicate webhook IDs must short-circuit before any ledger side effect."""
    code = _strip_comments(source)
    handler = re.search(r"export\s+async\s+function\s+handleWebhook\s*\(", code)
    if not handler:
        return ["the webhook handler was not found"]

    module_scope = code[:handler.start()]
    handler_body = code[handler.start():]
    signature_check = re.search(r"await\s+verifyWebhookSignature\s*\(\s*req\s*\)", handler_body)
    state_guard = re.search(
        r"if\s*\(\s*shopState\.hasWebhookEvent\s*\(\s*event\.id\s*\)\s*\)\s*\{",
        handler_body,
    )
    processed_set = None
    add_event = None

    if state_guard:
        guard_start, guard_open_end = state_guard.start(), state_guard.end()
    else:
        set_decl = re.search(
            r"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+Set(?:<[^;]*>)?\s*\(\s*\)\s*;",
            module_scope,
        )
        if not set_decl:
            return ["the webhook deduplication guard was not found"]
        processed_set = set_decl.group(1)
        seen = re.search(
            rf"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*{re.escape(processed_set)}\.has\s*\(\s*event\.id\s*\)\s*;",
            handler_body,
        )
        if not seen:
            return ["the webhook deduplication guard was not found"]
        duplicate_guard = re.search(
            rf"if\s*\(\s*{re.escape(seen.group(1))}\s*\)\s*\{{",
            handler_body[seen.end():],
        )
        if not duplicate_guard:
            return ["the webhook deduplication guard was not found"]
        guard_start = seen.end() + duplicate_guard.start()
        guard_open_end = seen.end() + duplicate_guard.end()
        add_event = re.search(
            rf"{re.escape(processed_set)}\.add\s*\(\s*event\.id\s*\)",
            handler_body,
        )

    return_at = handler_body.find("return;", guard_open_end)
    if return_at < 0:
        return ["the webhook deduplication guard does not return"]

    duplicate_reply = handler_body[guard_open_end:return_at]
    problems = []
    if "DUPLICATE_IGNORED" not in duplicate_reply:
        problems.append("the duplicate webhook is not acknowledged as ignored")
    if not re.search(r"res\.status\s*\(\s*200\s*\)", duplicate_reply):
        problems.append("the duplicate webhook is not acknowledged with HTTP 200")
    if not signature_check or signature_check.start() > guard_start:
        problems.append("webhook deduplication runs before signature verification")

    guard_end = return_at + len("return;")
    side_effects = [handler_body.find(op) for op in ("shopState.recordWebhookEvent", "shopState.recordCaptureSuccess")]
    side_effects = [position for position in side_effects if position >= 0]
    if side_effects and min(side_effects) < guard_end:
        problems.append("the webhook deduplication guard does not precede side effects")

    if processed_set:
        if not add_event:
            problems.append("the processed-event set is never updated")
        else:
            add_start = add_event.start()
            if add_start < guard_end or (side_effects and add_start > min(side_effects)):
                problems.append("the processed-event set is updated outside the safe path")

    if not side_effects:
        problems.append("the webhook handler side effects were not found")

    capture_record = re.search(r"shopState\.recordCaptureSuccess\s*\(", handler_body)
    order_capture_guard = re.search(
        r"if\s*\(\s*\(\s*shopState\.getOrder\(orderId\)\?\.captureCount\s*\|\|\s*0\s*\)\s*===\s*0\s*\)",
        handler_body,
    )
    if not order_capture_guard or (capture_record and order_capture_guard.end() > capture_record.start()):
        problems.append("capture webhook can repeat a capture already recorded by checkout")
    return problems


CHECKS: Dict[str, Callable[[str], List[str]]] = {
    "BUG-01": check_bug_01,
    "BUG-03": check_bug_03,
    "BUG-09": check_bug_09,
}


def check_patched(bug_id: str, source: str) -> List[str]:
    """Problems found in the patched source. Raises KeyError if no check exists for this bug yet."""
    return CHECKS[bug_id](source)
