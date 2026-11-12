<p align="center">
  <img src="docs/assets/readme-cover.svg" alt="DriftGuard tests a payment failure, compares PayPal and shop records, and reruns the fix" width="100%" />
</p>

<p align="center">
  <a href="https://driftguard-dashboard.onrender.com">Hosted explorer</a> ·
  <a href="evals/fixer/results/live-fixer-eval.md">Sandbox evidence</a> ·
  <a href="docs/devpost.md">Project story</a> ·
  <a href="LICENSE">MIT License</a>
</p>

<p align="center"><strong>PayPal AI Hackathon · Team Pixentropy</strong></p>

---

## Why DriftGuard exists

A payment request can reach PayPal while its success response disappears on the way back. The shop sees a timeout and has to decide whether to retry. Retrying blindly can create a second order; treating the timeout as a failure can leave a paid order unfulfilled.

DriftGuard recreates that failure against a deliberately vulnerable shop in **PayPal Sandbox**. It compares the Sandbox order with the shop's own record, then checks a proposed repair against a fresh order.

## Evidence from the demo shop

| Fault | How it breaks the flow & what the first run exposed | Curated patch rerun |
|:--|:--|:--|
| **F1 · lost capture response** | PayPal captured `38.97 USD` (`HTTP 201`), then mitmproxy dropped the reply as `HTTP 504`; blind retry hit `422` and left the shop at `0` captures | **PASS** · shop queried order state and recorded `1` capture matching PayPal |
| **F2 · simulated gateway timeout** | Proxy delayed the first order-create response (`1s`) and returned `HTTP 504`; retrying without `PayPal-Request-Id` created `2` Sandbox orders for `1` checkout | **PASS** · stable idempotency key yielded `1` order and `1` capture |
| **F3 · declined instrument** | Proxy forced `422 INSTRUMENT_DECLINED` on capture; unpatched handler still marked the order completed (`1` shop capture vs `0` in PayPal) | **PASS** · decline surfaced as failed checkout with `0` captures on both sides |
| **F4 · invoice response fault** | Proxy returned a simulated `409 DUPLICATE_INVOICE_ID` when an unstable invoice ID collided; shop failed to reconcile its order capture | **PASS** · deterministic cart-hashed invoice + idempotent retry gave `1` capture each |
| **F5 · tax rounding** | Floating-point tax calculation dropped 4 cents on checkout (`$38.92` requested and captured in Sandbox vs `$38.96` expected) | **PASS** · exact integer-cent tax calculation captured `$38.96` on a fresh order |
| **F6 · webhook replay** | Runner sent the same `PAYMENT.CAPTURE.COMPLETED` webhook twice; without deduplication the shop processed both deliveries while PayPal held `1` capture | **PASS** · event ID deduplication accepted the first delivery and ignored the replay |
| **F7 · refund prompt injection** | Adversarial buyer chat prompt bypassed prompt-only instructions and recorded an unauthorized `$500.00` simulated refund in shop state (PayPal had `0` refunds) | **PASS** · `$15.00` / admin role guard returned HTTP `403` and blocked the refund |

These results are seven local Sandbox runs, one curated-patch rerun per fault. For F5–F7, each row represents a fresh failed parent and a patched child using a distinct Sandbox order. The [evaluation record](evals/fixer/results/live-fixer-eval.md) contains the parent and child run IDs, PayPal evidence, and patch hashes. This is evidence for the seeded demo shop; it is not a model success rate or a study of other merchants.

F4 simulates an invoice response failure; it does not reproduce PayPal's own duplicate-invoice rejection. F6 tests whether the shop processes one webhook event twice; replay does not create another PayPal capture. F7's attack and guard are shop-state behavior; the demo does not call PayPal's refund API.

## The test, step by step

| 01 · Create | 02 · Disrupt | 03 · Compare | 04 · Rerun |
|:--|:--|:--|:--|
| Playwright approves a real Sandbox order as a test buyer. | mitmproxy delays or changes the response selected by the fault scenario. | The reconciler reads PayPal order evidence and the shop's per-order state. | A curated or model-proposed patch is applied to a temporary shop copy; a fresh order checks the behavior again. |

```text
PayPal Sandbox  ⇄  mitmproxy  ⇄  demo shop
                                      │
Playwright buyer ──► run engine ──► reconciler ──► saved run ──► dashboard
                                      ▲
                      patched shop copy + fresh order
```

The reconciler decides PASS, FAIL, or ERROR from observed state. The model can suggest a patch or explain a result; it does not decide the verdict.

## Run it locally

The hosted site is a fixture explorer. For a real Sandbox checkout, use the full local setup below. If you just want to browse the dashboard UI without Docker or PayPal credentials, jump to [Quick local UI preview](#quick-local-ui-preview-mock-fixtures).

### Prerequisites

* **Python 3.11+**, **Node.js 20.19+ or 22.12+ / npm** (`22.12+` for running dashboard tests), and **Git** on `PATH` (used to check and apply candidate diffs)
* **Docker Desktop** (runs PostgreSQL 16 and mitmproxy 10.2)
* **PayPal Developer Sandbox** REST credentials (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`) and a Sandbox personal buyer account (`PAYPAL_SANDBOX_BUYER_EMAIL`, `PAYPAL_SANDBOX_BUYER_PASSWORD`)
* *(Optional)* `ANTHROPIC_API_KEY` (or `GEMINI_API_KEY` / `GROQ_API_KEY`) for AI Studio replies and model-generated fixes; local run execution and curated-patch verification do not require a model key

### Full Sandbox setup

1. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell or `cp .env.example .env` in bash) and fill in your PayPal Sandbox REST credentials and Sandbox buyer account. Keep `.env` only on your machine.

2. From the repository root, install dependencies, download Playwright's Chromium browser, and start PostgreSQL + mitmproxy:

```powershell
python -m pip install -r engine/requirements.txt
python -m pip install -r ai/fixer/requirements.txt
python -m playwright install chromium
npm install --prefix targets/demo-shop
npm install --prefix dashboard
docker compose up -d
```

3. Start these four processes in separate terminals:

```powershell
python -m uvicorn engine.api.main:app --port 8000 --reload
python -m uvicorn ai.service.app:app --port 8001 --reload
npm --prefix targets/demo-shop run dev
npm --prefix dashboard run dev
```

Open `http://localhost:5173/` for the landing page and `http://localhost:5173/live` for engine runs. From another terminal, run:

```powershell
python -m cli run F1
python -m cli report --all
```

The first command returns a nonzero exit code when the seeded bug is found: `1` means FAIL and `2` means ERROR or no verdict. PostgreSQL is used when available; the API reports a persistent SQLite fallback if it cannot connect. The active proxy fault is shared, so run scenarios one at a time.

The Studio service on port 8001 needs `ANTHROPIC_API_KEY` for Claude replies (without it, Studio returns HTTP 503, while local run execution, curated fixes with `DRIFTGUARD_LLM=none`, and reconciliation still work). The dashboard reads `VITE_API_URL` and `VITE_AI_URL` from `dashboard/.env.local` when you use non-default addresses. Never put PayPal or model secrets in `VITE_` variables.

### Verify a patch locally

Patch execution is opt-in because it runs Node code. In `.env`, set:

```dotenv
DRIFTGUARD_ENABLE_FIX_RERUN=1
DRIFTGUARD_LLM=none
```

Restart the engine, open a failed run, and choose **Generate and verify fix**. With `DRIFTGUARD_LLM=none`, the fixer selects a curated patch. The engine applies it to a disposable copy, builds that copy, and tests a new Sandbox order. Keep this option off on public services; the temporary directory is not a security sandbox.

### Quick local UI preview (mock fixtures)

To inspect the dashboard locally without Docker or PayPal Sandbox credentials (Python 3.11+ and Node.js 20.19+ / 22+ only):

1. Start `mock_runner` in Terminal 1:
   ```powershell
   python -m pip install -r mock_runner/requirements.txt
   python -m uvicorn mock_runner.app:app --port 8000
   ```
2. Point the dashboard's AI/fix endpoints at `mock_runner` by adding these two non-secret lines to `dashboard/.env.local`:
   ```dotenv
   VITE_AI_URL=http://localhost:8000
   VITE_DEMO_MODE=sample
   ```
3. Start the dashboard in Terminal 2:
   ```powershell
   npm install --prefix dashboard
   npm --prefix dashboard run dev
   ```

Open `http://localhost:5173/` to explore the F1–F7 fixtures locally. Remove `dashboard/.env.local` before switching back to the full 4-terminal Sandbox setup.

## Hosted explorer

The [Render site](https://driftguard-dashboard.onrender.com) uses `mock_runner`, which serves contract fixtures and prepared outcomes. Its run, fix, and verify controls let visitors explore the interface; they do not run Playwright, mitmproxy, patch code, or make a new PayPal payment. Responses are labeled `mode: "sample"` in the dashboard.

The hosted API can call Anthropic if `ANTHROPIC_API_KEY` is set as a Render secret. Put an account or workspace spend limit in Anthropic Console before adding the key. The service's in-memory request limits reset on restart and do not cap billing. Without the key, Studio returns a prepared answer and identifies it as a preview.

## Project map

| Path | Purpose |
|:--|:--|
| `engine/` | FastAPI run API, orchestration, proxy rules, and deterministic reconciliation |
| `targets/demo-shop/` | Deliberately vulnerable TypeScript checkout used as the test target |
| `targets/known-fixes/` | Curated patches used by offline verification |
| `ai/` | Buyer driver, pattern-based scanner, scenario generator, fixer, and explainer |
| `contracts/` | Scenario/result schemas plus examples; fixtures are not live payment evidence |
| `dashboard/` | React interface, AG Grid run table, and AG Studio canvas |
| `mock_runner/` | Fixture-backed API for the hosted explorer |
| `evals/` | Automated checks and saved evaluation artifacts |

The scanner currently uses source patterns, not Tree-sitter. The demonstrated live path covers PayPal Orders create/capture and order evidence. Webhook signature verification, real PayPal refunds, and real duplicate-invoice rejection are outside the saved proof. The [study data](study/methodology.md) is exploratory annotation data; the repository does not contain enough source and run records to support population statistics.

## Tools & sponsor integrations

* **PayPal Sandbox & `@paypal/paypal-server-sdk`:** Powers Orders v2 create/capture in `targets/demo-shop/`, real Sandbox buyer approvals via Playwright, `PayPal-Request-Id` idempotency tests, `PayPal-Mock-Response` decline headers, `PAYMENT.CAPTURE.COMPLETED` webhook payloads, and authoritative order/capture ledger verification in `engine/reconciler/`.
* **AG Studio (`ag-studio` / `ag-studio-react` by AG Grid):** Renders the interactive analytics workspace and Ask Studio chat canvas in `/live/studio` (with `AgGridReact` components also in `dashboard/`).
* **APIMatic Context:** Consulted during development to check `@paypal/paypal-server-sdk 2.0.0` signatures inside `ai/fixer/prompt.py` (`SDK_NOTES`). It is not a runtime dependency.
* **Render:** Hosts the two-service interactive preview (`driftguard-dashboard` static CDN + `driftguard-api` running `mock_runner`).
* **Anthropic Claude (`claude-haiku-5-5`, with optional Gemini / Groq failover):** Powers **Ask Studio** (`POST /llm/messages` with `list_runs` and `explain_run` tools) to diagnose drift from stored evidence, and can draft candidate fixes/explanations in `ai/` behind deterministic diff and behavior gates.
* **Core Stack:** Python (`FastAPI`, `Pydantic`, `mitmproxy`, `Playwright`, `pytest`), TypeScript/Node.js (`Express`, `React`, `Vite`, `Vitest`), and `PostgreSQL` / `SQLite`.

## Team

| Teammate | Focus |
|:--|:--|
| [Swastik Bose](https://github.com/VasuBhakt) | Engine and reconciliation |
| [Kiran Patra](https://github.com/patrakiran) | Scenarios and demo shop |
| [Prathamesh Prasad](https://github.com/Prathamesh51-debug) | Fixer, dashboard, and buyer driver |

The [ownership map](docs/repo-ownership.md) describes review boundaries. The [planner](docs/planner.md) is historical; it records intended work, not current feature status.
