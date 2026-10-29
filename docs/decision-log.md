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
