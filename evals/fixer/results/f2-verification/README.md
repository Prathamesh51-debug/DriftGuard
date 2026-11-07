# F2 reference and Claude fix verification — 2026-11-07

This evidence verifies both the Role C bundled patch in
`ai/fixer/known_fixes/BUG-02.diff` and the separately generated `claude.patch`.
The Claude proposal used Anthropic with caching and curated fallback disabled;
the accepted patch was applied without manual source edits.

## Live PayPal Sandbox comparison

| Execution | Verdict | PayPal orders | Captures | Amount |
|---|---|---|---|---|
| Original shop | FAIL | 2 | 1 | 38.97 USD |
| Reference-patched isolated copy | PASS | 1 | 1 | 38.97 USD |
| Claude-patched isolated copy | PASS | 1 | 1 | 38.97 USD |

- Baseline orders: `76L87672MM062444L`, `80X35732P55256529`.
  Capture: `1VF296521J0818601`.
- Patched order: `3LP638034S8744902`. Capture: `8X2037865V1992622`.
- A second, independent 38.97 USD purchase created `60G62327PU9648826` with a
  different request ID. Its injected failure and retry returned that same new
  order. This second purchase was not approved or captured.
- Claude-patched order: `15344380HP753464P`. Capture: `18581002F8734361V`.
  Its second, independent 38.97 USD purchase created `51F54489MB573662R` with
  a different request ID, stable across its retry. This second purchase was
  also not approved or captured.

The audit files show a genuine upstream order response replaced with HTTP 504,
followed by a retry. The original has no request ID and creates two order IDs.
The patched retries have identical request IDs, request-body hashes, and order IDs.
Result JSON and audit JSONL are preserved alongside this report; no credentials
or authorization headers are included.

## Claude generation provenance

- Configured model: `claude-haiku-5-5`; provider: `anthropic`.
- One fresh proposal session; its second attempt passed the patch acceptance
  checks. This is one verified sample, not an estimated model success rate.
- Input: the original checkout source, the canonical F2 scenario/failure
  fixtures, bug metadata, and fixer prompt including SDK guidance. The saved
  live baseline result was not the model input.
- `claude-proposal.json` and `claude.patch` preserve the accepted normalized
  proposal. The existing patcher applies with `git apply --recount`, so model
  hunk counts need not be exact; no semantic patch edits were made afterward.
- `claude-verification.json` records configuration, checks, and SHA-256 hashes
  of normalized text for the inputs, patch, and executed checkout source.
  Its spend total is the local guard's cumulative estimate, not this run's bill.

## Execution method

Used the existing `engine.orchestrator.runner.run_scenario` with
`contracts/fixtures/f2_scenario.json`: original shop on port 3001, an isolated
copy with the exact bundled patch on port 3002, both through the live chaos proxy.
The reference copy was stopped and removed before starting a separate copy with
the exact accepted Claude patch on port 3002; it used the same execution method.
Buyer approval used the existing Playwright driver, then the shop captured and
the reconciler queried PayPal. The original demo-shop source was not changed.

For each execution the harness recorded the starting byte offset of
`logs/proxy_traffic.jsonl`. At reconciliation it saved only subsequent entries
and passed that file as `reconcile_order(..., log_path=...)`. This avoids the
existing reconciler's global 120-second log window mixing order IDs from the
previous run. The actual timestamps and entries were preserved. Executions were
sequential. The harness restored the previous active-fault file afterward.

These direct orchestrator calls were not persisted through the engine HTTP API
and therefore do not add dashboard run rows.

## Local checks

- 86 tests passed across `ai/fixer/tests`, `evals/fixer`, and `contracts/tests`.
- Both the reference-patched and Claude-patched shops compiled with `npm run build`
  and passed the runtime harness.
- `check_f2_runtime.cjs` executes the patched TypeScript with the SDK boundary
  stubbed to lose the first response. It checks identical keys and complete
  request bodies on retry, distinct keys for equal-price purchases, and one
  recorded order per completed purchase. The same harness rejects seeded code.
- Static checks reject missing, amount-derived, literal, and regenerated keys,
  and fields regenerated inside the retry loop. They recognize supported source
  shapes; they are not a general proof of arbitrary generated code.

## Scope and limitations

- The active F2 proxy waits 1000 ms and substitutes HTTP 504 after PayPal creates
  the order. The fixture describes a 6000 ms delay. This proves recovery from
  the active lost-response mechanism, not a six-second client socket timeout.
- The key is stable within one `createCheckoutOrder` invocation. Deduplication
  across separate client HTTP calls or process restarts needs a persisted
  purchase identity and is outside this patch.
- The separate BUG-04 invoice behavior and Role B target patch remain unchanged.
  The fixer now prefers this verified Role C fallback for BUG-02.
- This completes one live Claude-generated F2 fix proof for the active proxy
  mechanism. It does not establish reliability across repeated model samples
  or resolve the broader engine/fixture and persistence limitations above.
