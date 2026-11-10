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


def check_bug_02(source: str) -> List[str]:
    """BUG-02: reuse one per-purchase request ID and identical order fields across retries."""
    code = _strip_comments(source)
    handler = re.search(r"export\s+async\s+function\s+createCheckoutOrder\s*\(", code)
    if not handler:
        return ["the order-creation handler was not found"]
    create_code = re.split(r"\nexport\s+(?:async\s+)?function\s+", code[handler.end():], maxsplit=1)[0]
    call = re.search(r"ordersController\.createOrder\s*\(\s*\{([\s\S]*?)\}\s*\)", create_code)
    if not call:
        return ["the createOrder call was not found"]

    args = call.group(1)
    field = re.search(r"\bpaypalRequestId\b(?:\s*:\s*([^,}\n]+))?", args)
    if not field:
        return ["createOrder is still called without paypalRequestId"]

    request_id = (field.group(1) or "paypalRequestId").strip()
    if not re.fullmatch(r"[A-Za-z_$][\w$]*", request_id):
        return ["the request ID must be a per-purchase variable reused across retries"]
    key_decl = re.search(
        rf"\bconst\s+{re.escape(request_id)}\s*=\s*((?:crypto\.)?randomUUID\s*\(\s*\)|[^;]+);",
        create_code,
    )
    loop = re.search(r"\bwhile\s*\([^)]*\battempts\b[^)]*\)\s*\{", create_code)
    problems = []
    if not key_decl:
        problems.append("the request ID must be unique per purchase; do not derive it from amount alone")
    else:
        if not re.fullmatch(r"(?:crypto\.)?randomUUID\s*\(\s*\)", key_decl.group(1).strip()):
            problems.append("the request ID must be unique per purchase; do not derive it from amount alone")
        if loop and key_decl.start() > loop.start():
            problems.append("the request ID must be created once before the retry loop")

    body_decl = re.search(r"\bconst\s+body\s*=\s*\{", create_code)
    uses_body_variable = bool(re.search(r"\bbody\s*(?:,|\})", args))
    stable_body = bool(body_decl and loop and body_decl.start() < loop.start() and uses_body_variable)
    if not stable_body:
        if not loop:
            problems.append("the retry loop was not found")
        else:
            for field_name in ("referenceId", "invoiceId"):
                value = re.search(rf"\b{field_name}\s*:\s*([A-Za-z_$][\w$]*)\b", args)
                shorthand = re.search(rf"(?<![\w$]){field_name}(?![\w$])(?=\s*[,}}])", args)
                variable = value.group(1) if value else (field_name if shorthand else None)
                declaration = (
                    re.search(rf"\bconst\s+{re.escape(variable)}\s*=\s*[^;]+;", create_code)
                    if variable else None
                )
                if not declaration or declaration.start() > loop.start():
                    problems.append("referenceId and invoiceId must keep the same order body on every retry")
                    break
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


def check_bug_04(source: str) -> List[str]:
    """BUG-04: stable invoice for a cart, distinct invoices for equal-price purchases."""
    code = _strip_comments(source)
    handler = re.search(r"export\s+async\s+function\s+createCheckoutOrder\s*\(", code)
    if not handler:
        return ["the order-creation handler was not found"]
    create_code = re.split(r"\nexport\s+(?:async\s+)?function\s+", code[handler.end():], maxsplit=1)[0]
    loop = re.search(r"\bwhile\s*\([^)]*\battempts\b[^)]*\)\s*\{", create_code)
    call = re.search(r"ordersController\.createOrder\s*\(\s*\{([\s\S]*?)\}\s*\)", create_code)
    if not loop or not call:
        return ["the createOrder retry call was not found"]
    args = call.group(1)
    cart = re.search(r"\bconst\s+cartId\s*=\s*([^;]+);", create_code)
    invoice = re.search(r"\bconst\s+invoiceId\s*=\s*([^;]+);", create_code)
    problems = []
    if not cart or cart.start() > loop.start() or not re.search(r"options\?\.cartId|options\.cartId", cart.group(1)) or not re.search(r"\brandomUUID\s*\(", cart.group(1)):
        problems.append("cart identity must use a supplied cartId or a new UUID before retries")
    if not invoice or invoice.start() > loop.start() or not all(part in invoice.group(1) for part in ("createHash", "cartId", "finalAmount")):
        problems.append("invoice ID must hash cart identity and final amount before retries")
    if not re.search(r"\binvoiceId\s*(?:,|:\s*invoiceId\b)", args):
        problems.append("createOrder does not use the stable invoice ID")
    ref_direct = re.search(r"\breferenceId\s*:\s*cartId\b", args)
    ref_variable = re.search(r"\bconst\s+referenceId\s*=\s*([^;]+);", create_code)
    ref_stable = bool(
        ref_variable and ref_variable.start() < loop.start()
        and "cartId" in ref_variable.group(1)
        and re.search(r"\breferenceId\s*(?:,|:\s*referenceId\b)", args)
    )
    if not ref_direct and not ref_stable:
        problems.append("the order reference must use the same cart identity")
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


def check_bug_10(source: str) -> List[str]:
    """BUG-10: reject over-limit buyer refunds before recording any shop refund."""
    code = _strip_comments(source)
    handler = re.search(r"export\s+async\s+function\s+handleChat\s*\(", code)
    if not handler:
        return ["the chat handler was not found"]
    body = code[handler.start():]
    guard = re.search(
        r"if\s*\(\s*requestedAmount\s*>\s*(\d+(?:\.\d+)?)\s*&&\s*userRole\s*!==\s*['\"]admin['\"]\s*\)\s*\{",
        body,
    )
    if not guard:
        return ["the over-limit buyer role guard was not found"]
    try:
        limit = float(guard.group(1))
    except ValueError:
        return ["the refund policy limit is not numeric"]
    problems = []
    if limit <= 0 or limit > 15:
        problems.append("the buyer refund limit is missing or above the $15 policy")
    return_at = body.find("return;", guard.end())
    refund_at = body.find("shopState.recordRefund", guard.end())
    if return_at < 0 or (refund_at >= 0 and return_at > refund_at):
        problems.append("the rejected request can reach shopState.recordRefund")
    guard_block = body[guard.end():return_at] if return_at >= 0 else ""
    if not re.search(r"res\.status\s*\(\s*403\s*\)", guard_block):
        problems.append("an over-limit buyer request is not rejected with HTTP 403")
    if not re.search(r"refundTriggered\s*:\s*false", guard_block):
        problems.append("the rejection response does not state refundTriggered=false")
    return problems


CHECKS: Dict[str, Callable[[str], List[str]]] = {
    "BUG-01": check_bug_01,
    "BUG-02": check_bug_02,
    "BUG-03": check_bug_03,
    "BUG-04": check_bug_04,
    "BUG-09": check_bug_09,
    "BUG-10": check_bug_10,
}


def check_patched(bug_id: str, source: str) -> List[str]:
    """Problems found in the patched source. Raises KeyError if no check exists for this bug yet."""
    return CHECKS[bug_id](source)
