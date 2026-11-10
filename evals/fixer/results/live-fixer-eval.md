# Fixer evaluation — 9 November 2026

## Product red-to-green path

The engine generated a curated patch in offline mode (`DRIFTGUARD_LLM=none`),
applied it to a disposable shop copy, built that copy, ran the same fault
through the proxy, and reconciled a **new** PayPal Sandbox order. The original
shop source was not modified. `product-live-runs.json` preserves the stored
parent/child IDs, per-order observations, PayPal order IDs, patch source, and
SHA-256; the exporter checked each parent FAIL, child PASS, relationship, patch
hash, and distinct PayPal orders.

| Fault / bug | Original run | Verified child | Original | Patched | What changed |
|---|---|---|---|---|---|
| F1 / BUG-01 | `run_7c57cf96` | `run_3a4ac1fb` | FAIL | PASS | PayPal 1 capture, app 0 → PayPal 1, app 1 |
| F2 / BUG-02 | `run_ed40390f` | `run_8783b452` | FAIL | PASS | 2 PayPal orders → 1; one $38.97 capture |
| F3 / BUG-03 | `run_46846457` | `run_99ddee6a` | FAIL | PASS | Declined capture: PayPal 0, app 1 → PayPal 0, app 0 |
| F4 / BUG-04 | `run_f965ce33` | `run_7b6002ba` | FAIL | PASS | PayPal 1 capture, app 0 → PayPal 1, app 1 |

**Observed product result: 4/4 patched reruns passed, one attempt per bug.**
This is a small demo sample of curated fallbacks, not a measured reliability
claim for model generation. A child is labeled fixed only when its stored patch
hash exists and its deterministic reconciler verdict is PASS. Manual polling
was at four to five second intervals; the product API does not yet persist a
completion timestamp, so precise time-per-fix statistics are unavailable.
Observed complete local reruns took roughly 25–35 seconds. Do not treat that
range as a latency benchmark.

## Model-generated patches

The model-only evaluation disables curated fallback and cache. Its historical
source checks measure whether a generated diff applies and matches the checks
used for that evaluation; they do **not** prove acceptance by the current
product gate or a live Sandbox outcome.

| Bug | Fresh model samples passing source checks | Avg model generation | Live model patch evidence |
|---|---:|---:|---|
| BUG-01 | 10/10 | 7.5 s | No saved live model-patch rerun in this evaluation |
| BUG-03 | 3/3 | 8.3 s | 1 archived Claude patch: PASS; 23.5 s build + Sandbox verification |
| BUG-09 | 2/3 | 10.1 s | No live model-patch rerun here |

The BUG-03 source check table is `BUG-03-anthropic.md`. Its archived patch is
`model-patches/BUG-03-anthropic.patch`. The exact patch was replayed without a
new model call using `verify_saved_patch.py`; `f3-verification/claude-live.json`
records its hash, source hash, PayPal order, observed state and 23.5-second
build-and-run time. BUG-01 and BUG-09 source tables are separate artifacts.

An archived BUG-01 Claude candidate (SHA-256
`935c07a418bd5226a2a66c3e2e02b9da7f799a740e9897135fea4ee6c3cbc673`)
was replayed through the current product verifier. Its diff applied, but the
behavior gate rejected it before build or Sandbox execution: it adds a stable
`paypalRequestId` without checking PayPal order status after an ambiguous
capture error. Thus the historical BUG-01 `10/10` source-check result is not
a live fix pass rate. An archived BUG-09 candidate also applies, but its
current behavior check rejects it because a capture webhook can repeat a
capture already recorded by checkout. No live model-patch PASS is claimed for
BUG-01 or BUG-09. The rejected BUG-09 candidate's SHA-256 is
`1bbe1d7e752850d548add3ce4f4bbf7b44a5355b3aeb8e9961fa56223d6c0b43`.

Earlier direct live tests of one Claude-generated patch each for BUG-02 and
BUG-04 passed; see `f2-verification/README.md` and
`f4-verification/README.md`. Their cached replies and curated fallback were
disabled, and their patches were saved. BUG-04 also passed a second independent
equal-price purchase. These are **one accepted model sample per bug**, not a
repeated live model pass-rate estimate. The direct runs were not stored through
the dashboard API.

## Additional local Sandbox runs — 10 November 2026

F5–F7 were run sequentially through the local engine, mitmproxy, demo shop, and
PayPal Sandbox. Each patched child used a fresh Sandbox order. The engine used
curated offline patches (`DRIFTGUARD_LLM=none`); no Anthropic model call was
made for these runs.

| Fault / bug | Original run | Verified child | Original | Patched | PayPal observation |
|---|---|---|---|---|---|
| F5 / BUG-05 | `run_ebb4eaa4` | `run_22e8683d` | FAIL · $38.92 | PASS · $38.96 | Order `15D529906R651360B` → `9AF32480U3527900U`; one capture each. Patch SHA-256: `0584e1f728292497e44e3cff0887af0b5662264eff3aff8c97d3db44856ebb48`. |
| F6 / BUG-09 | `run_a65379d0` | `run_8e418d1b` | FAIL · event delivered twice | PASS · event delivered once | Order `6GX56635YJ4874153` → `0K9952839N919113H`; one PayPal capture each. Patch SHA-256: `a246c3800e14f268d5f7aaa48c4436c44d93cfe176f7d66b1b6be3fd3a5f2483`. |
| F7 / BUG-10 | `run_c337b012` | `run_67131ddf` | FAIL · shop recorded refund request | PASS · guard denied request | Order `9ED39583JB535684V` → `51T99723V5567134W`; one PayPal capture each, zero PayPal refunds. Patch SHA-256: `f12aed906c0aa0be04d6c54e918edebd92313f73d8991d36b73609264be96024`. |

For F6, the duplicate is application webhook processing: PayPal still has one
capture. For F7, the seeded shop originally recorded a simulated refund request;
the patched shop denies it. Neither run calls PayPal's Refund API. Earlier
attempts that errored before creating a PayPal order are excluded. Together
F1–F7 now have one curated patch red-to-green pair each in the local Sandbox.

## Limits that remain

- F2's active proxy substitutes HTTP 504 after a 1-second wait. The scenario
  fixture was later corrected from 6 seconds to 1 second; the saved live proof
  covers the active 1-second mechanism.
- F4's active proxy simulates an invoice response failure. It does not prove
  handling of PayPal's actual duplicate-invoice error. The shop currently
  creates a new cart identity when its HTTP route receives no `cartId`, so
  retry identity across separate client requests is still unproven.
- The proxy fault control is shared. These runs were sequential. Concurrent
  runs would need isolation or a scheduler lock before their verdicts could be
  compared reliably.
- A source check is a bounded code-shape check. The live reconciler, not the
  model, decides PASS or FAIL.
