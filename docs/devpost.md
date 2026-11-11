# DriftGuard · submission copy

**Repository:** https://github.com/Prathamesh51-debug/DriftGuard
**Hosted explorer:** https://driftguard-dashboard.onrender.com
**Team:** Swastik Bose, Kiran Patra, Prathamesh Prasad

## What we built

A checkout request can reach PayPal even when its response never reaches the merchant. That leaves the merchant with a hard question: did the buyer pay, or should the app try again? A blind retry can create another payment. A blind failure can leave a paid order unfulfilled.

DriftGuard makes that uncertainty testable. We built a TypeScript demo shop with deliberate payment bugs, a mitmproxy fault injector, a Playwright Sandbox buyer, a runner, and a reconciler. The runner creates a PayPal Sandbox order and triggers a fault. The reconciler reads PayPal order evidence and the shop's state, then produces a deterministic PASS, FAIL, or ERROR. The React dashboard makes the mismatch visible. A patch verifier can apply a proposed fix to a temporary copy of the shop, build it, and run a **new** Sandbox checkout.

Our most useful lesson was that a successful API response and a successful payment are different facts. For F1, the shop lost the capture response while PayPal held a capture. The first run showed PayPal with one capture and the shop with none. After a curated patch, a fresh order showed one capture on both sides. The same local patch-and-rerun flow passed once each across all seven faults (F1–F7), using a fresh PayPal Sandbox order per rerun. [Saved run IDs, patch hashes, and limitations](../evals/fixer/results/live-fixer-eval.md) are in the repository.

## What the demo shows

The **hosted Render site is an interactive explorer of recorded examples**. It uses a fixture-backed API so a judge can browse the interface without Sandbox accounts or Docker. Hosted launch, fix, and verify actions present prepared sample outcomes; they do not make PayPal calls or execute patched code. Studio can optionally call Anthropic from the server when a key is configured; otherwise its answer is labeled as prepared. For live fault injection, run the repository locally using the [README](../README.md), or inspect the saved F1–F7 evidence in the [evaluation report](../evals/fixer/results/live-fixer-eval.md).

| Scenario | How DriftGuard breaks & checks it | Evidence status |
|---|---|---|
| **F1 · lost capture response** | Lets PayPal capture (`201`), then drops the reply at mitmproxy (`504`); catches unfulfilled paid orders when a blind retry hits `422` (`1` PayPal capture vs `0` in shop) | Local Sandbox FAIL → PASS saved |
| **F2 · simulated gateway timeout** | Delays the first order-create response (`1s`) and injects `HTTP 504`; catches duplicate Sandbox orders created when retries omit `PayPal-Request-Id` | Local Sandbox FAIL → PASS saved |
| **F3 · declined instrument** | Forces `422 INSTRUMENT_DECLINED` on capture; catches false-fulfillment bugs where the shop logs a completed capture despite `$0.00` collected | Local Sandbox FAIL → PASS saved |
| **F4 · invoice response fault** | Injects a simulated `409 DUPLICATE_INVOICE_ID` when invoice IDs collide or vary across retries; verifies deterministic cart-hashed invoice identity and single capture | Local Sandbox FAIL → PASS saved; simulated proxy fault, not real PayPal duplicate-invoice rejection |
| **F5 · tax rounding** | Catches floating-point cent truncation in checkout tax calculation (`$38.92` captured vs `$38.96` expected) by comparing PayPal's ledger against decimal math | Local Sandbox FAIL → PASS on fresh orders |
| **F6 · webhook replay** | Replays the same `PAYMENT.CAPTURE.COMPLETED` webhook twice to verify idempotent deduplication (`1` processed delivery vs `2`; PayPal stays at `1` capture) | Local Sandbox FAIL → PASS; single PayPal capture in both runs |
| **F7 · prompt injection** | Sends an adversarial buyer chat prompt asking for an unapproved `$500.00` refund; checks that deterministic role + `$15.00` code guardrails reject it | Local Sandbox FAIL → PASS; shop-side guard only, no PayPal Refund API call |

## How we used the tools

- **PayPal Sandbox Orders** supplied the create, approve, capture, and order evidence for the local live runs. The demo shop is a controlled target, not a general PayPal integration scanner.
- **mitmproxy** supplied fault timing and response substitution. Its active fault setting is shared, so the saved runs were sequential.
- **Playwright** approved Sandbox orders as a buyer during local runs.
- **Anthropic Claude** can propose patches, explain failures through Studio chat, and analyze observed evidence. The verdict always comes from deterministic code that compares PayPal and shop state. The seven saved product reruns in the table used curated patches (`DRIFTGUARD_LLM=none`); separate single-candidate Claude patch evaluations are linked in the [evaluation report](../evals/fixer/results/live-fixer-eval.md).
- **AG Grid Community and AG Studio** present the run ledger and an interactive analysis canvas. The grid is a way to inspect evidence, not the mechanism that decides PASS.
- **APIMatic context** was consulted while developing SDK guidance. It is not a runtime dependency in the hosted demo or a source of an automatically verified patch.

## What was difficult

The first temptation was to call every mismatch a PayPal failure. We had to separate the payment network from our own target shop. A webhook delivered twice can duplicate the shop's work, but it cannot create a second PayPal capture. The F7 assistant can set a refund flag in the demo shop, but that is not a real refund. We tightened the fixtures and wording to keep those boundaries visible.

The patch loop needs a second, distinct order. A diff that applies, compiles, or looks plausible is only a candidate. The result matters after the patched shop meets the same fault and the reconciler reads the new order. We keep patch hashes and parent/child run IDs so that this step can be checked.

## What comes next

All seven faults (F1–F7) now have verified local Sandbox parent/child pairs saved in the [evaluation report](../evals/fixer/results/live-fixer-eval.md). Next, we plan to isolate mitmproxy fault settings per run for concurrent test execution, enforce container/VM isolation before allowing patch verification reruns on a public host, and expand beyond the seeded TypeScript shop with AST-level scanning.

**Video link:** add the public three-minute video URL to the Devpost submission when it is ready. No video asset is stored in this repository.
