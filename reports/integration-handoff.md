# Integration handoff · 10 November 2026

## Saved live evidence

The local engine has stored F1–F7 failed parent runs and passing child runs on distinct PayPal Sandbox orders after curated patches. The [fixer evaluation](../evals/fixer/results/live-fixer-eval.md) gives exact run IDs, patch hashes, observations, and separate Claude candidate evidence. These runs were sequential. They do not measure reliability on other shops.

The Explainer evaluated four saved Sandbox failures with Claude. Its [result note](../evals/explainer/results/README.md) records the bounded claim check. The [projector check](projector-qa.md) covers local Chromium layout only.

## Remaining integration gates

| Gate | Current state | Evidence needed |
|---|---|---|
| F5 amount | Verified. Parent `run_ebb4eaa4` failed at $38.92; child `run_22e8683d` passed at $38.96 on a new Sandbox order. | Closed for the seeded shop. BUG-05 patch hash and PayPal IDs are in the evaluation report. |
| F6 replay | Verified. Parent `run_a65379d0` recorded the same event twice; child `run_8e418d1b` recorded it once. PayPal showed one capture in each run. | Closed for the seeded shop. Replay cannot create a second PayPal capture. |
| F7 assistant | Verified. Parent `run_c337b012` recorded one shop-side refund request; child `run_67131ddf` rejected it. PayPal's refund list was empty in both runs. | Closed for the shop-side guard. This does not test the PayPal Refund API. |
| F4 semantics | The active proxy substitutes an invoice response failure. | Keep the simulation label, or capture a separate real PayPal duplicate-invoice response. |
| F2 timing | Scenario fixture and active proxy now both specify a one-second delay before the proxy substitutes HTTP 504. | A new live timing trace would confirm the delay in a fresh run. |
| Hosted preview | Render blueprint uses the fixture API. Public execution of patched code is disabled. | Verify the currently deployed URL and Studio behavior; use local Docker for live Sandbox runs. |

F5–F7 were run sequentially through the local engine, proxy, shop, and PayPal Sandbox. Earlier ERROR attempts that failed before an order was created are excluded from the proof. Concurrent runs remain unsupported because proxy fault selection is shared.

## Decisions and tradeoffs

- Keep the seeded shop bugs. Removing them would make the demo look safer by eliminating the test target, not by repairing it. Apply fixes only to a temporary copy during verification.
- Keep the hosted API fixture-backed. Public patch execution would run generated Node code; an isolated worker and abuse controls are required before exposing that path.
- Count F6 webhook deliveries in an event history, while retaining a set for deduplication. A set alone made the duplicate invisible to the reconciler. A duplicated event is an app-processing fault, not a second PayPal charge.
- Scope F7 shop refunds to the current order and keep their IDs out of `paypal_refund_ids`. Otherwise an earlier shop-only refund could fail a new run or be misreported as a PayPal refund.
