# Fault injection handlers — one module per fault type.
# Each module exposes: arm_request(flow) and inject_response(flow) -> bool

from . import f1_lost_capture
from . import f2_slow_paypal
from . import f3_forced_decline
from . import f4_duplicate_invoice
from . import f5_money_math
from . import f6_webhook_replay
from . import f7_prompt_injection

__all__ = [
    "f1_lost_capture",
    "f2_slow_paypal",
    "f3_forced_decline",
    "f4_duplicate_invoice",
    "f5_money_math",
    "f6_webhook_replay",
    "f7_prompt_injection",
]

