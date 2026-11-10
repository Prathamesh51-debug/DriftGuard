# Integration handoff · 10 November 2026

## Saved live evidence

The local engine has stored F1–F4 failed parent runs and passing child runs on distinct PayPal Sandbox orders after curated patches. The [fixer evaluation](../evals/fixer/results/live-fixer-eval.md) gives exact run IDs, patch hashes, observations, and separate Claude candidate evidence. These runs were sequential. They do not measure reliability on other shops.

The Explainer evaluated four saved Sandbox failures with Claude. Its [result note](../evals/explainer/results/README.md) records the bounded claim check. The [projector check](projector-qa.md) covers local Chromium layout only.

## Remaining integration gates

| Gate | Current state | Evidence needed |
|---|---|---|
| F5 amount | Runner now sends the `35.99` subtotal and tax rate, not the expected `38.96` as the checkout input. BUG-05 patch context matches the current seeded rounding code. Unit tests and shop build pass. | Fresh failed and patched Sandbox orders with exact PayPal totals and patch hash. |
| F6 replay | Runner uses the capture ID from the checkout and a unique event ID per order. Shop state now exposes repeated event deliveries rather than collapsing them to a set. Reconciler checks one PayPal capture and whether the shop processed the replay twice. Unit tests and shop build pass. | Fresh failed and patched Sandbox orders; verify the same event is recorded twice before and once after BUG-09. Replay alone cannot create a PayPal capture. |
| F7 assistant | The shop records refund requests locally. The reconciler scopes them to the current order and keeps app-only IDs out of PayPal refund evidence. A failed chat request returns ERROR rather than a false PASS. | Fresh local run and patch rerun. State clearly that no PayPal refund API is called. |
| F4 semantics | The active proxy substitutes an invoice response failure. | Keep the simulation label, or capture a separate real PayPal duplicate-invoice response. |
| F2 timing | Scenario fixture and active proxy now both specify a one-second delay before the proxy substitutes HTTP 504. | A new live timing trace would confirm the delay in a fresh run. |
| Hosted preview | Render blueprint uses the fixture API. Public execution of patched code is disabled. | Verify the deployed URL and Studio behavior after deployment; use local Docker for live Sandbox runs. |

The current session could run unit tests and the TypeScript build, but Docker's daemon was unavailable, so it did not add new live Sandbox evidence for F5–F7.

## Decisions and tradeoffs

- Keep the seeded shop bugs. Removing them would make the demo look safer by eliminating the test target, not by repairing it. Apply fixes only to a temporary copy during verification.
- Keep the hosted API fixture-backed. Public patch execution would run generated Node code; an isolated worker and abuse controls are required before exposing that path.
- Count F6 webhook deliveries in an event history, while retaining a set for deduplication. A set alone made the duplicate invisible to the reconciler. A duplicated event is an app-processing fault, not a second PayPal charge.
- Scope F7 shop refunds to the current order and keep their IDs out of `paypal_refund_ids`. Otherwise an earlier shop-only refund could fail a new run or be misreported as a PayPal refund.
