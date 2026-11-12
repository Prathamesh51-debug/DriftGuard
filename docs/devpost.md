# DriftGuard · Devpost submission copy

**Repository:** https://github.com/Prathamesh51-debug/DriftGuard
**Hosted explorer:** https://driftguard-dashboard.onrender.com
**Team:** Swastik Bose, Kiran Patra, Prathamesh Prasad

## Inspiration

In online checkouts, an API response and real money movement are two different facts. A capture call can reach PayPal and settle funds while the HTTP reply disappears on the way back due to a gateway timeout or proxy drop. That leaves the merchant's backend guessing: retry blindly and risk creating a duplicate payment, or fail the checkout and leave a paying customer with an unfulfilled order.

Most test suites rely on happy-path mocks that never catch this mismatch until production ledgers go out of sync. We built **DriftGuard** to make silent payment state drift testable, visible, and deterministically verifiable against real PayPal Sandbox transactions.

## What it does

DriftGuard is a checkout reliability and fault-verification harness built around a four-step loop (**Create → Disrupt → Compare → Rerun**):

1. **Create:** A headless Playwright buyer navigates and approves a real PayPal Sandbox order against a deliberately vulnerable TypeScript demo shop.
2. **Disrupt:** `mitmproxy` intercepts live checkout traffic and injects **7 real-world failure modes (F1–F7)**:

| Scenario | How DriftGuard breaks & checks it | Evidence status |
|---|---|---|
| **F1 · lost capture response** | Lets PayPal capture (`201`), then drops the reply at mitmproxy (`504`); catches unfulfilled paid orders when a blind retry hits `422` (`1` PayPal capture vs `0` in shop) | Local Sandbox FAIL → PASS saved |
| **F2 · simulated gateway timeout** | Delays the first order-create response (`1s`) and injects `HTTP 504`; catches duplicate Sandbox orders created when retries omit `PayPal-Request-Id` | Local Sandbox FAIL → PASS saved |
| **F3 · declined instrument** | Forces `422 INSTRUMENT_DECLINED` on capture; catches false-fulfillment bugs where the shop logs a completed capture despite `$0.00` collected | Local Sandbox FAIL → PASS saved |
| **F4 · invoice response fault** | Injects a simulated `409 DUPLICATE_INVOICE_ID` when invoice IDs collide or vary across retries; verifies deterministic cart-hashed invoice identity and single capture | Local Sandbox FAIL → PASS saved; simulated proxy fault, not real PayPal duplicate-invoice rejection |
| **F5 · tax rounding** | Catches floating-point cent truncation in checkout tax calculation (`$38.92` captured vs `$38.96` expected) by comparing PayPal's ledger against decimal math | Local Sandbox FAIL → PASS on fresh orders |
| **F6 · webhook replay** | Replays the same `PAYMENT.CAPTURE.COMPLETED` webhook twice to verify idempotent deduplication (`1` processed delivery vs `2`; PayPal stays at `1` capture) | Local Sandbox FAIL → PASS; single PayPal capture in both runs |
| **F7 · prompt injection** | Sends an adversarial buyer chat prompt asking for an unapproved `$500.00` refund; checks that deterministic role + `$15.00` code guardrails reject it with `HTTP 403` | Local Sandbox FAIL → PASS; shop-side guard only, no PayPal Refund API call |

3. **Compare:** A deterministic reconciler queries PayPal Sandbox order evidence and the shop's per-order state, producing an objective `PASS`, `FAIL`, or `ERROR` verdict with exact monetary impact.
4. **Rerun:** DriftGuard applies a proposed patch to a disposable copy of the shop, compiles TypeScript, and runs a **brand-new PayPal Sandbox order** under the same fault to prove the bug is fixed.

The [hosted Render explorer](https://driftguard-dashboard.onrender.com) (`mock_runner`) lets judges inspect prepared `F1`–`F7` outcomes, run ledger evidence, and test **Ask Studio** without Docker or Sandbox credentials, while the full engine runs locally against real PayPal Sandbox.

## How we built it

* **Core Engine & Chaos Proxy (`engine/`):** Built with **FastAPI**, **PostgreSQL / SQLite**, a `SKIP LOCKED` background worker, a PayPal REST order evidence client, a deterministic reconciler, and a zero-restart **mitmproxy** chaos router.
* **Target Testbed (`targets/demo-shop/`, `targets/known-fixes/`):** An Express + TypeScript checkout using `@paypal/paypal-server-sdk`, seeded with intentional payment bugs (`BUG-01`–`BUG-10`) and curated patches.
* **Automation, Fixer & Explainer (`ai/`):**
  * **Playwright** automates Sandbox buyer approvals (`ai/buyer_driver/`).
  * **Anthropic Claude** (`claude-haiku-5-5`, with optional Gemini and Groq failover) powers **Ask Studio** (`POST /llm/messages` with tool calls like `list_runs` and `explain_run`) to explain root causes from stored evidence, and can draft candidate patch diffs in `ai/fixer/` (validated by diff safety checks, behavior gates, and curated fallback).
  * **APIMatic Context** was consulted during development to verify `@paypal/paypal-server-sdk 2.0.0` parameter names (`captureOrder`, `getOrder`, `paypalRequestId`) inside the fixer's `SDK_NOTES` guidance. It is not a runtime dependency.
* **Dashboard & Studio UI (`dashboard/`):** Built with **React**, **TypeScript**, **Vite**, and **AG Studio (`ag-studio` / `ag-studio-react`)** for interactive data analysis, Before-and-After comparison sliders, run filtering, and light/dark theming.

## Challenges we ran into

* **Separating PayPal's ledger from shop state:** Early on, it was easy to conflate application bugs with network failures. For instance, replaying a webhook (`F6`) duplicates the shop's processing without creating a second PayPal capture, and `F7` tests shop-side refund guardrails rather than PayPal's Refund API. We tightened every reconciler rule, fixture, and UI label to keep those boundaries explicit.
* **Proving fixes beyond syntax:** A patch that applies cleanly and compiles with `tsc` is only a candidate—some model-proposed `F1` patches added idempotency headers without querying PayPal order status after a timeout. We added behavior checks (`evals/fixer/checks.py`) and required every verified fix to pass on a fresh PayPal Sandbox order with a stored patch SHA-256 and parent/child run link.
* **Environment & cross-service debugging:** We caught and resolved `httpx2` + `Brotli 1.1.0` decompression crashes (`mitmproxy` dependency conflict) in the Anthropic SDK client, scoped synthetic webhook IDs per order without dropping real PayPal event UUIDs, and prevented React polling updates from stealing focus inside AG Studio's AI panel.

## Accomplishments that we're proud of

* **End-to-end Sandbox proof across all 7 fault classes (`F1`–`F7`):** Recorded local PayPal Sandbox `FAIL` → `PASS` parent/child pairs with stored order IDs, capture IDs, and patch SHA-256 hashes (using curated patches in offline mode `DRIFTGUARD_LLM=none`, plus archived single-candidate Claude reruns for `F2`–`F4`) in [`evals/fixer/results/live-fixer-eval.md`](../evals/fixer/results/live-fixer-eval.md).
* **Covering the full payment risk spectrum:** Going beyond basic network timeouts (`F1`, `F2`) and decline/invoice bugs (`F3`, `F4`) to catch IEEE 754 tax rounding drift (`F5`), webhook replay processing (`F6`), and AI support prompt-injection refund bypasses (`F7`).
* **Strict separation of AI and ground truth ("AI proposes, code decides"):** Only deterministic reconciler code inspecting PayPal order evidence and shop state decides `PASS` or `FAIL`, and the Fixer requires both behavior checks and a fresh Sandbox checkout before a patch is marked verified.
* **An honest, zero-setup explorer alongside the local engine:** Anyone can click through `F1`–`F7` runs, evidence ledgers, and Claude-backed Ask Studio on Render (`mode: "sample"` clearly labeled), while engineers can reproduce real Sandbox chaos locally with Docker, `mitmproxy`, and Playwright.

## What we learned

* **Idempotency keys alone don't heal dropped responses:** When we tested model-generated `F1` fixes, some patches added `PayPal-Request-Id` without querying PayPal order status (`getOrder`) after a timeout—meaning PayPal stayed at `1` capture while the shop's database remained at `0`. Reconciling upstream state before retrying is non-negotiable.
* **Compiling is a weak bar for AI-generated patches:** A unified diff can apply cleanly and pass `tsc` while still failing the underlying payment invariant. Combining diff gates, behavioral checks, and a live rerun on a fresh order caught subtle failures that static checks missed.
* **Prompt instructions cannot guard financial actions:** On `F7`, buyer-facing prompt rules gave way to adversarial phrasing; only deterministic backend caps (`$15.00` limit) and role checks (`HTTP 403` for non-admins) kept simulated refunds safe.
* **Clear boundaries build trust in payment tooling:** Being explicit about where PayPal Sandbox ends and proxy or shop simulation begins (`F4`, `F6`, `F7`) made our architecture cleaner, our tests stricter, and our demo completely verifiable.

## What's next for DriftGuard

* **Per-run proxy isolation:** Scoping `mitmproxy` fault rules by request/run context so scenarios can run concurrently instead of sequentially.
* **Isolated public execution:** Adding container/microVM boundaries so patch build-and-verify reruns can execute safely on public hosts without local setup.
* **Broader SDK & AST scanning:** Expanding the pattern-based scanner to full Tree-sitter AST analysis beyond the seeded TypeScript demo shop, and extending live fault coverage to real duplicate-invoice rejections, webhook signature verification, and PayPal Refund/Dispute APIs.

**Video link:** add the public three-minute video URL to the Devpost submission when it is ready. No video asset is stored in this repository.
