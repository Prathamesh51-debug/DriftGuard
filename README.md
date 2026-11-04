# DriftGuard

**The autonomous chaos-testing and sandbox ledger-reconciliation harness for AI payment agents.**  
Built for the PayPal AI Hackathon 2026.

[![PayPal AI Hackathon](https://img.shields.io/badge/PayPal_AI_Hackathon-2026-003087?style=for-the-badge)](https://paypalaihackathon.devpost.com/)
[![Built with APIMatic](https://img.shields.io/badge/APIMatic-Context_Plugin-10A37F?style=for-the-badge)](#)
[![Powered by AG Grid Community](https://img.shields.io/badge/AG_Grid-Community-5B9DFF?style=for-the-badge)](#)

## The Problem
Wiring language models to payment APIs introduces subtle, high-severity distributed systems bugs that mocked unit tests miss. When an AI agent drops an HTTP packet mid-capture, rounds a fractional tax calculation by $0.04, or receives a spoofed dispute webhook, it drifts from reality. The agent tells the user one thing, the local database records another, and the PayPal ledger reflects a third—often resulting in catastrophic double-charges or unauthorized refunds.

## What DriftGuard Does
DriftGuard is a live runtime fuzzer and MITM fault-injector for `api-m.sandbox.paypal.com`. It intercepts live sandbox traffic from your AI application, injects real-world network and semantic faults, and mathematically proves whether your agent's deterministic guardrails hold. 

1. **Scan:** Parses your repository's AST to map PayPal SDK call sites (`Orders v2`, `Invoicing v2`, `Webhooks`).
2. **Attack:** A reverse proxy injects 504 Gateway Timeouts, duplicate invoices, and malicious prompt-injection payloads into your live sandbox traffic.
3. **Reconcile:** Bypasses your local database to query PayPal's Sandbox Ground Truth directly, generating a 3-way state diff in a high-density AG Grid dashboard.
4. **Fix:** Uses the APIMatic Context Plugin to synthesize and apply drop-in code patches (e.g., deriving deterministic SHA-256 `PayPal-Request-Id` headers).

## Load-Bearing Tech Stack
* **PayPal APIs:** `Orders v2`, `Invoicing v2`, `Captures Refund API`, `Transaction Search`, `verify-webhook-signature`.
* **Execution Kernel:** `mitmproxy` (fault injection), PostgreSQL (`SKIP LOCKED` concurrent job queues), Docker.
* **AI & AST:** Anthropic Claude (semantic evaluation), `tree-sitter` (code mapping), APIMatic Context Plugin (SDK patch generation).
* **Frontend Dashboard:** React, AG Grid (live 3-way ledger reconciliation), AG Studio.

## Measured Impact
**[X] out of 25 public AI payment apps we tested double-charged buyers on a network timeout.** 
*Methodology:* We ran DriftGuard's F1 (Lost Capture Response) chaos scenario against 25 anonymized, open-source AI commerce repositories built during this hackathon. [Y] applications failed to implement deterministic idempotency keys, resulting in duplicate Sandbox captures when the HTTP connection was severed mid-flight.

## Quick Start

### Open the dashboard with fixture data

This starts the dashboard against the local mock API. It does not call PayPal or an LLM.

1. Start the mock API from the repository root:
   ```bash
   pip install -r mock_runner/requirements.txt
   uvicorn mock_runner.app:app --port 8000
   ```
2. In another terminal, start the dashboard:
   ```bash
   cd dashboard
   npm install
   npm run dev
   ```
3. Open `http://localhost:5173/` for the API-backed dashboard. `/live` is an equivalent direct route.

### Connect the real engine

Copy `.env.example` to `.env` and configure the sandbox and model-provider credentials. `make up` starts Postgres and mitmproxy; it does not start the API or dashboard. Start the engine API separately with `make api`, then run the dashboard as above. The dashboard defaults to `http://localhost:8000`; set `VITE_API_URL` if the API is hosted elsewhere.

## Repository Structure
* `/engine` - The MITM proxy, deterministic reconciler, and API orchestrator.
* `/ai` - Tree-sitter AST scanner, scenario generator, and APIMatic fixer.
* `/dashboard` - The AG Grid command center and visual ledger.
* `/targets/demo-shop` - A deliberately vulnerable sandbox commerce app seeded with 10 exact bugs to test the harness.
* `/contracts` - Shared Pydantic schemas validating the JSON pipeline between the AI and the execution engine.

See [`docs/repo-ownership.md`](docs/repo-ownership.md) for who leads and reviews each folder, and [`docs/planner.md`](docs/planner.md) for the day-by-day execution plan.

## Contributors

Team Pixentropy 

- [Swastik Bose](https://github.com/VasuBhakt)
- [Kiran Patra](https://github.com/patrakiran)
- [Prathamesh Prasad](https://github.com/Prathamesh51-debug)
