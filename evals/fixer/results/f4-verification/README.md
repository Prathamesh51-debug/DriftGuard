# F4 / BUG-04 fixer verification — 2026-11-09

This comparison used the original demo shop and two independent copies of its
checkout source: one with `ai/fixer/known_fixes/BUG-04.diff`, and one with the
exact accepted `claude.patch`. The model proposal used Anthropic with reply
caching and curated fallback disabled. The accepted patch applied on its first
model attempt; it was not edited before execution.

| Execution | F4 verdict | PayPal capture | Shop capture | Invoice |
|---|---|---|---|---|
| Original | FAIL | 1 × $38.97 | 0 | `INV-389290` |
| Role C reference fix | PASS | 1 × $38.97 | 1 | `INV-BFAE51C4744BDAD8` |
| Claude fix, purchase 1 | PASS | 1 × $38.97 | 1 | `INV-2ff9fee464ac70add3a56b4054d65be2b862bff3d2cfbb0847246ef3efdc84b1` |
| Claude fix, separate equal-price purchase | PASS | 1 × $38.97 | 1 | `INV-144283611d2cc48b5efcc28a238750684c02132d4a5651238dd9c93e49e7143c` |

Order and capture IDs, invoice IDs, and amounts were read back from the PayPal
Sandbox Orders API and saved in `paypal-orders.json`. Each run's proxy audit and
reconciler result are saved here. The audit slices begin at each run's log byte
offset so the reconciler does not mix prior test orders into this run. All
executions were sequential. The F4 proxy was active; the original shop used
port 3001, the reference copy port 3002, and the Claude copy port 3003. Buyer
approval used the existing Playwright driver. These direct orchestrator runs
were not persisted to the dashboard database.

The original run is a **simulated response failure**: the proxy received a real
PayPal capture HTTP 201, then returned an injected HTTP 409 to the app because
the invoice matched its `INV-` followed by digits rule. PayPal captured $38.97;
the shop recorded zero. This does **not** prove that PayPal detected a real
duplicate invoice. The two patched runs avoid that proxy rule and reconcile one
capture each. The second equal-price purchase proves the accepted Claude patch
did not reuse the first purchase's invoice ID.

The original Role C reference patch used `Date.now()` when no cart ID was
provided, allowing two checkouts in one millisecond to collide. The verified
reference patch uses a UUID for that fallback. The runtime harness fixes the
clock, checks the same cart produces the same invoice, different equal-price
carts produce different invoices, and a retry reuses the complete body. It
rejects the seeded code and accepts both patched copies. The source checker
also rejects the seeded invoice, an amount-only hash, and a timestamp fallback;
it is a limited source-shape check, not a general semantic proof. The model
patch built with TypeScript and passed the same runtime harness.

Known integration limits:

- The shop HTTP `/api/orders` handler does not currently pass a client `cartId`
  through to `createCheckoutOrder`. The function supports a supplied stable
  cart ID, but the live runs used a new UUID for each request. This does not
  prove idempotency across separate client HTTP retries or process restarts.
- In the second Claude run the reconciler's `amount_captured` field reported
  **$77.94**. PayPal's order and its single capture were **$38.97**. The
  reconciler takes the larger of this order's PayPal capture and the shop's
  aggregate total across both completed purchases. Its F4 verdict checks
  capture counts only. This amount-reporting issue belongs to Role A and
  should be corrected before using repeated-run totals in a public demo.
- F4 still tests a proxy-defined invoice format and response substitution.
  It does not establish how the fixer handles an actual PayPal
  `DUPLICATE_INVOICE_ID` response from a previously paid invoice.

Local validation: **107 tests passed** across `ai/fixer/tests`, `ai/service`,
`evals/fixer`, and `contracts/tests`. Both patched shops built with TypeScript.
The model patch, source hashes, run results, proxy audits,
and PayPal order summaries are preserved in this directory for review.
