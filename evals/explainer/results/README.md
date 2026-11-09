# Live Explainer evaluation — 9 November 2026

The inputs were four completed failing engine runs against PayPal Sandbox:
F1 `run_7c57cf96`, F2 `run_0c90e05d`, F3 `run_46846457`, and
F4 `run_c7a3a466`. Each run supplied its stored Scenario and Result to the
Explainer. Fresh `claude-haiku-5-5` replies used the configured Anthropic API,
with reply caching off and the existing spend guard on. The model chose words;
code checked every numeric figure and PayPal-style ID against the Result.

| Measure | Corrected evaluation |
|---|---:|
| Accepted without regeneration | 4/4 (100%) |
| Accepted after regeneration | 0/4 |
| Template fallback | 0/4 |
| Final outputs passing numeric/ID grounding | 4/4 |
| Mean model response time | 3.6 seconds |
| Added local spend-guard estimate | $0.0012 |

`live-explainer-eval.json` contains the per-run reply, provider, attempts,
rejections, time, grounding result, and cumulative spend-guard values. It is
an evaluation artifact, not a displayed demo script. All four final replies
were also read manually for whether they accurately separated PayPal records
from app records and described the active proxy fault. This is a four-case
sample, so 100% here is **not** an estimated general model reliability rate.

## Red-team correction

The first evaluation (`live-explainer-eval-before.json`) also passed numeric
and ID checks 4/4, but manual review found two unsupported claims: F2 stated
that the fixture's 6000 ms delay happened live although the proxy uses a
different active delay; F4 described an actual duplicate-invoice collision
although the proxy simulated an app-facing failure. That run demonstrates why
numeric grounding alone is insufficient for causal claims.

The reconciler now describes only observed order/capture facts for F2/F4. The
prompt labels the fault as a test plan, and the verifier rejects unsupported
attached timing figures and F4 collision claims. Fresh F2/F4 Sandbox failures
were captured after those changes, then the four-case evaluation was rerun.
The corrected outputs make no unsupported timing or PayPal-invoice-error claim.

The verifier still cannot prove every sentence true: number words, vague causal
claims, and omissions require review. The fallback template is deterministic;
its F3 branch was corrected to say that the app falsely recorded a payment
that PayPal did not capture. Seventeen Explainer tests and the live run
exercise these protections.
