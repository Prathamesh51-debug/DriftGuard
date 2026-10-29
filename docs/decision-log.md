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

