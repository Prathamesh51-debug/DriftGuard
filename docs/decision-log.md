# DriftGuard Architecture & Engineering Decision Log

*Format: Append-only ledger of architecture decisions, spike outcomes, and critical path consensus.*

---

## [2026-10-29] Spike 1 Outcome: PayPal-Mock-Response Verification
- **Author:** Role A (Engine)
- **Status:** APPROVED / PASSED
- **Trace Debug ID:** `3fc230ceac4f5`

### Context
Per `planner.md` (Part 5, Phase 0 Go/No-Go #1), we needed to determine whether the PayPal Sandbox honors negative testing via the `PayPal-Mock-Response` HTTP header on capture calls, or whether we would have to fall back to synthetic proxy-only error injection for Faults F3 (Decline) and F4 (Duplicate Invoice).

### Experiment
1. Authenticated against `https://api-m.sandbox.paypal.com/v1/oauth2/token`.
2. Created a `$10.00 USD` order (`POST /v2/checkout/orders`).
3. Completed buyer approval via sandbox browser.
4. Executed capture (`POST /v2/checkout/orders/{id}/capture`) with header:
   ```http
   PayPal-Mock-Response: {"mock_application_codes": "INSTRUMENT_DECLINED"}
   ```

### Result & Verdict
- **HTTP Status:** `422 Unprocessable Entity`
- **Issue Code:** `INSTRUMENT_DECLINED`
- **PayPal Debug ID:** `3fc230ceac4f5`
- **Verdict:** **PASSED**. The sandbox mock engine reliably intercepts captures and produces the exact banking decline error payload.

### Impact on Pipeline
- **No Fallback Needed:** We will use native `PayPal-Mock-Response` headers for F3 (Instrument Declined) and F4 (Duplicate Invoice ID).
- **Audit ID Established:** Confirmed that PayPal returns `debug_id` even on 422 declines, satisfying Rule #2 (*"Every verdict traces to PayPal IDs"*).


---

## [2026-10-29] Spike 2 Outcome: mitmproxy Reverse Mode Interception
- **Author:** Role A (Engine)
- **Status:** APPROVED / PASSED
- **Trace Request ID:** `driftguard-spike2-d6a21455`

### Context
Per `planner.md` (Part 5, Phase 0 Go/No-Go #2), verify that `mitmproxy` in reverse mode (`--mode reverse:https://api-m.sandbox.paypal.com`) successfully intercepts HTTPS sandbox calls, forwards requests transparently to PayPal without SSL negotiation failure, and extracts `PayPal-Request-Id` for audit logging.

### Experiment
1. Spun up Docker Compose service `proxy` with `mitmproxy/mitmproxy:10.2.0` in reverse mode on ports 8080 (traffic) and 8081 (mitmweb UI).
2. Loaded addon `engine/proxy/addons/logger.py` to inspect HTTPFlow objects.
3. Executed `engine/spikes/spike_2_proxy_test.py` pointing at `http://localhost:8080/v1/oauth2/token` with header `PayPal-Request-Id: driftguard-spike2-d6a21455`.

### Result & Verdict
- **HTTP Status:** `200 OK`
- **Access Token:** Received valid PayPal sandbox access token.
- **mitmweb Telemetry:** Complete flow inspected at `http://localhost:8081` showing Host header rewriting, `PayPal-Request-Id`, and 733B payload.
- **Verdict:** **PASSED**. Reverse proxy architecture verified; base interceptor ready for F1-F4 chaos addon implementations.

---

## [2026-10-29] Phase 1 Vertical Slice: F1 Lost Capture & JSONL Audit Log
- **Author:** Role A (Engine)
- **Status:** APPROVED / GATE CLEARED
- **Order ID:** `2EY23628X22941825`
- **Real PayPal Capture ID:** `3SR16091KV8213005`
- **Injected Status:** `HTTP 504 Gateway Timeout`

### Context
Per `planner.md` (Part 6: Phase 1 Vertical Slice), implement Proxy v1 with JSONL structured audit logging and Fault F1 (`drop_response`) action. Validate that the proxy intercepts an approved capture, lets PayPal charge the account (201), drops the response (substituting 504 Timeout), and captures the real capture ID in `logs/proxy_traffic.jsonl`.

### Experiment & Verification
1. Loaded `engine/proxy/addons/f1_lost_capture.py` into `driftguard-proxy` with mounted `./logs` volume.
2. Executed `engine/spikes/test_f1_lost_capture.py`.
3. Completed buyer approval for order `2EY23628X22941825`.
4. Triggered capture with `X-DriftGuard-Fault: F1` and `PayPal-Request-Id: driftguard-f1-c71314bc`.

### Result & Verdict
- **Client Observed:** `HTTP 504 Gateway Timeout`
- **PayPal Sandbox Ledger:** `COMPLETED` (`3SR16091KV8213005`)
- **JSONL Audit Trail:** Validated in `logs/proxy_traffic.jsonl` with SHA-256 body hash `e3b0c442...` and duration `2218ms`.
- **Verdict:** **GATE CLEARED**. The proxy reliably separates app-perceived failure from actual PayPal financial state.

---

## [2026-10-29] Spike 3 Outcome: Headless Playwright Buyer Approval
- **Author:** Role C (AI + Fixes)
- **Status:** APPROVED / PASSED
- **Result:** 10/10 approved and captured with no human, ~12s per run

### Context
Per `planner.md` (Part 5, Phase 0 Go/No-Go #3), chaos runs cannot wait for a person to click through PayPal's approval page. We needed to know whether headless Playwright can log in as the sandbox buyer, approve an order, and reach the return URL reliably.

### Experiment
1. Authenticated against `https://api-m.sandbox.paypal.com` and created a `$10.00 USD` order with `return_url` set to `http://localhost:3000/return`.
2. Opened the order's `payer-action` link in headless Chromium, logged in as the sandbox Personal buyer, and clicked *Complete Purchase*.
3. Waited for the redirect to the return URL (nothing listens there, so the request is stubbed in the browser).
4. Captured the order (`POST /v2/checkout/orders/{id}/capture`) and checked for `201 COMPLETED`.
5. Repeated 10 times, then re-ran through the Python module `ai/buyer_driver/` (5/5).

### Result & Verdict
- **Pass rate:** 10/10 in the Node spike, 5/5 through `ai/buyer_driver/live_check.py`.
- **Duration:** ~11-14s per run in the spike, ~8-9s through the Python module.
- **Verdict:** **PASSED**. No fallback needed; pre-approved orders are not required for the demo or video.

### Impact on Pipeline
- **Module:** `ai/buyer_driver/approve_order(approve_url, return_url)` returns an `ApprovalResult`. It stops at the redirect and does not capture, so the orchestrator's capture call stays visible to the proxy.
- **Selectors:** `#email`, `#btnNext`, `#password`, `#btnLogin`, and the *Complete Purchase* button. All live in `ai/buyer_driver/paypal_selectors.py` so a PayPal page change is a one-file fix.
- **Hand-off:** A can call the driver from the orchestrator (due 30 Oct). `ApprovalResult` is local until `contracts/` defines it.

---

## [2026-10-29] Spike 5 Outcome: APIMatic Context Plugin for SDK Patch Generation
- **Author:** Role C (AI + Fixes)
- **Status:** APPROVED / PASSED
- **Result:** Guidance matches the SDK typings; sample compiles under `tsc --strict`

### Context
Per `planner.md` (Part 5, Phase 0 Go/No-Go #5), the Fixer needs the APIMatic Context Plugin to give correct PayPal SDK usage, so patches use real method names and parameters. If it failed, the fallback was hand-written patch templates.

### Experiment
1. Installed the plugin in Claude Code (`/plugin marketplace add apimatic/context-matic`, then `/plugin install context-matic@apimatic`) and completed the browser OAuth login. The server is hosted at `https://chatbotapi.apimatic.io/mcp/plugins`.
2. `fetch_api` (typescript, key `paypal`) returned the PayPal Server SDK.
3. `ask`: "capture an order idempotently so a retried capture after a network timeout does not double charge".
4. `endpoint_search` (`captureOrder`) and `model_search` for the request and response shapes.
5. Installed `@paypal/paypal-server-sdk@2.0.0` in a scratch folder, compared the plugin's `captureOrder` signature with the real typings, and compiled its sample with `tsc --strict`.

### Result & Verdict
- **Guidance:** Use the same `paypalRequestId` on the capture and on any retry. The SDK sends it as the `PayPal-Request-Id` header. This is the F1 fix we need.
- **Signature match:** `captureOrder({ id, paypalMockResponse, paypalRequestId, prefer, paypalClientMetadataId, paypalAuthAssertion, body })` matches the typings exactly.
- **Compile check:** The sample compiles with no errors against SDK 2.0.0.
- **Verdict:** **PASSED**. The fallback patch templates are not needed.

### Impact on Pipeline
- **Fixer (C5):** Can draw SDK usage from `ask`, `endpoint_search` and `model_search`. Pin `@paypal/paypal-server-sdk@2.0.0`, the version the plugin recommends.
- **Known inaccuracy:** The plugin's text says a successful capture returns `200 OK`. Real sandbox captures return `201`. The Fixer and its checks must not assume `200`.
- **Access:** Each developer must install the plugin and complete the OAuth login once. `APIMATIC_API_KEY` in `.env.example` is not used by this server.


---

## [2026-11-02] Contracts v1.1 & F1 Ground Truth Realignment
- **Author:** Role B (AI + Attacks) in consensus with Role C (AI + Fixes)
- **Status:** APPROVED / CONSENSUS REACHED

### Context & Findings
Sandbox execution confirmed that retrying `OrdersController.captureOrder` without `PayPal-Request-Id` after a dropped HTTP 201 does **not** create a second capture. Instead, PayPal rejects the repeat capture with `422 Unprocessable Entity: ORDER_ALREADY_CAPTURED`. Because the target application only catches 504 and network errors, it breaks out of the retry loop and marks the order as `FAILED` (recording 0 captures), while the buyer was actually charged ($38.97 USD).

### Decisions & Changes
1. **Contracts (`contracts/models.py`, `schemas/`):**
   - Added `app_recorded_captures: Optional[int]` to `ObservedState` so that state drift between PayPal Sandbox records and local merchant application state is explicitly measurable.
   - Formally added `ApprovalResult` to `contracts/models.py` (standardizing Role C buyer driver outputs across the pipeline).
   - Exported updated JSON schemas via `contracts/export_schemas.py`.
2. **Fixtures & Rules (`contracts/fixtures/`):**
   - Updated `f1_result_fail.json`: PayPal captures = 1, amount = 38.97 USD, `app_recorded_captures` = 0. Rule updated to `app_recorded_captures == captures`.
   - Updated `f1_result_pass.json`: PayPal captures = 1, `app_recorded_captures` = 1, rule `app_recorded_captures == captures`.
3. **Demo Shop & Bug Catalog (`targets/demo-shop/`):**
   - Reworded `checkout.ts` header comments and `bugs.yaml` `BUG-01` failure mode to reflect the true failure ("Order lost / state drift" instead of "Double charge").
   - Fixed typo in `bugs.yaml` `BUG-03` ("Unhanded" -> "Unhandled").
4. **Known Fix (`targets/known-fixes/BUG-01.patch`):**
   - Regenerated with correct hunk counts and inline comment context.
   - Verified that `git apply --check targets/known-fixes/BUG-01.patch` passes cleanly without output.
5. **AI Common Adapter (`ai/common/`):**
   - Adopted the multi-provider LLM adapter into `ai/common/` (exporting Gemini, Groq, Anthropic with spend guard, fallback, and caching).
   - Re-exported all classes from `ai/fixer/` to maintain 100% backwards compatibility with Role C's tests.

---

## [2026-11-03] Role A Engine Core: Reconciler, Orchestrator & Database Layer
- **Author:** Role A (Engine)
- **Status:** APPROVED / IMPLEMENTED

### Context
Per `planner.md` (Part 2 & Part 6: Role Playbook A), the Engine needs:
1. A ground-truth Reconciler comparing PayPal REST records with target app state.
2. An Orchestrator coordinating the execution loop (Order -> Headless Buyer Driver -> Chaos Proxy -> Reconciler).
3. A persistent Database layer with `SKIP LOCKED` task queue semantics.
4. A FastAPI service (`engine/api/main.py`) replacing `mock_runner` on port 8000.

### Implementation Summary
1. **Reconciler (`engine/reconciler/`):**
   - `PayPalClient`: Authenticates via OAuth and fetches unadulterated order details directly from `https://api-m.sandbox.paypal.com/v2/checkout/orders/{id}`.
   - `reconcile_order()`: Harvests `PayPal-Request-Id` and hashes from `logs/proxy_traffic.jsonl`, queries target app `/_driftguard/state`, and computes `ObservedState`, `Evidence`, and deterministic `Result`.
   - Adheres strictly to Rule 1 ("AI proposes, code decides"): evaluates `app_recorded_captures == captures`.
2. **Database Layer (`engine/orchestrator/db.py`):**
   - Implements persistent run storage with PostgreSQL primary backend.
   - Includes `fetch_next_pending_run_skip_locked()` using `SELECT ... FOR UPDATE SKIP LOCKED` for crash-resilient worker concurrency.
   - Includes zero-configuration SQLite fallback (`driftguard.db`) for lightweight testing when PostgreSQL is paused.
3. **Orchestrator Runner (`engine/orchestrator/runner.py`):**
   - Coordinates end-to-end execution: creates order, calls Playwright headless buyer approval (`ai.buyer_driver`), triggers capture through chaos proxy, and executes reconciliation.
4. **API Service (`engine/api/main.py`):**
   - Exposes `/health`, `/runs`, `/runs/{id}`, and `/runs/{id}/rerun` directly compatible with the React + AG Grid Dashboard.

---

## [2026-11-03] Integration Milestone: First 100% Automated Red Result (Phase 1 Gate Cleared)
- **Author:** Role A (Engine)
- **Status:** GATE CLEARED / VERIFIED
- **Order ID:** `85P354300U488443F`
- **Real PayPal Capture ID:** `0SV2419179962062Y`
- **Approval Duration:** `17.53s` (Headless Playwright Chromium)
- **App Response:** `HTTP 502`
- **Verdict:** `FAIL`

### Context
Per `planner.md` (Part 4 & Part 6: Mon 2 Nov Integration Gate), achieve the first red result on the Demo Shop end-to-end with **zero manual steps**.

### Automated Sequence Observed
1. **Target Order Creation:** `POST http://localhost:3001/api/orders` returned PayPal Order `85P354300U488443F`.
2. **Headless Buyer Approval:** Role C Playwright driver (`ai.buyer_driver`) logged into Sandbox buyer and clicked Complete Purchase in `17.53s` without any human intervention.
3. **Chaos Interception & Dropped Response:** Target shop called capture. Proxy intercepted and dropped the `201 Created` response, injecting `504 Gateway Timeout`.
4. **BUG-01 Reproduction:** Demo shop retried capture blindly without `PayPal-Request-Id`. PayPal returned `422 UNPROCESSABLE_ENTITY (ORDER_ALREADY_CAPTURED)`. Demo shop recorded `0` captures in `/_driftguard/state`.
5. **Reconciliation:** Reconciler queried live PayPal Ground Truth (Captures = 1, $38.97 USD) and compared with app state (0).
6. **Verdict Emitted:** `FAIL: buyer charged, but app recorded 0 captures: 38.97 USD paid without fulfillment`.

---

## [2026-11-04] Integration Milestone: Fault F2 (Slow PayPal / Timeout) Verified Red
- **Author:** Role A (Engine)
- **Status:** GATE CLEARED / VERIFIED
- **Order IDs (PayPal Ground Truth):** `9983267541997254A` (Attempt 1), `9CX04545KS102981Y` (Attempt 2)
- **Real PayPal Capture ID:** `8KK6439477146883L`
- **Rule Evaluated:** `orders_created == 1`
- **Observed:** `orders_created = 2`, `captures = 1` ($38.97 USD)
- **Verdict:** `FAIL`
- **Money Impact:** `duplicate orders: 2 orders created in PayPal for single purchase without idempotency key`

### Context
Per `planner.md` (Part 7: Phase 2 Breadth), verify Fault F2 against `BUG-02` on the Demo Shop.

### Automated Sequence Observed
1. **Target Order Creation (Attempt 1):** Target shop initiated order creation. PayPal created Order `9983267541997254A`.
2. **Chaos Interception (F2):** Proxy intercepted response, delayed 1,000ms, and returned `HTTP 504 Gateway Timeout`.
3. **BUG-02 Reproduction:** Demo shop caught timeout and blindly retried `createOrder` without an idempotency key (`paypalRequestId`).
4. **Target Order Creation (Attempt 2):** PayPal treated the retry as a new transaction and created duplicate Order `9CX04545KS102981Y`.
5. **Headless Approval & Capture:** Playwright approved Order 2 in ~11s. Target shop captured Order 2 (`8KK6439477146883L`).
6. **Reconciliation:** Reconciler checked PayPal ledger evidence and discovered 2 orders were created in PayPal for a single user purchase.
7. **Deterministic Verdict:** `FAIL: duplicate orders: 2 orders created in PayPal for single purchase without idempotency key`.

---

## [2026-11-04] Integration Milestone: Fault F3 (Forced Decline / False Fulfillment) Verified Red
- **Author:** Role A (Engine)
- **Status:** GATE CLEARED / VERIFIED
- **Order ID (PayPal Ground Truth):** `4U145438683322506`
- **Real PayPal Captures:** `0` ($0.00 USD)
- **App Recorded Captures:** `1` (False Success on 422)
- **Rule Evaluated:** `app_recorded_captures == captures`
- **Verdict:** `FAIL`
- **Money Impact:** `state drift detected: expected 0 captures, got 0 in PayPal vs 1 in app (false fulfillment on INSTRUMENT_DECLINED)`

### Context
Per `planner.md` (Part 7: Phase 2 Breadth), verify Fault F3 against `BUG-03` on the Demo Shop.

### Automated Sequence Observed
1. **Target Order Creation:** Order created on PayPal Sandbox (`4U145438683322506`, $38.97 USD).
2. **Headless Approval:** Playwright approved payment in `14.31s`.
3. **Chaos Interception (F3):** Proxy intercepted `POST .../capture`, injected `PayPal-Mock-Response: {"mock_application_codes": "INSTRUMENT_DECLINED"}`, returning `HTTP 422 UNPROCESSABLE_ENTITY`.
4. **BUG-03 Reproduction:** Demo shop caught 422, mistakenly treated decline as handled/complete, recorded a successful capture locally in `/_driftguard/state`, and responded with `HTTP 200 OK`.
5. **Reconciliation:** Reconciler queried live PayPal records (0 captures, $0.00 paid) and merchant state (1 capture recorded).
6. **Deterministic Verdict:** `FAIL: state drift detected: expected 0 captures, got 0 in PayPal vs 1 in app (false fulfillment on INSTRUMENT_DECLINED)`.


