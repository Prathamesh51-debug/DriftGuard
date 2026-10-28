# DriftGuard

**The autonomous chaos-testing and sandbox ledger-reconciliation harness for AI payment agents.**  
Built for the PayPal AI Hackathon 2026.

[![PayPal AI Hackathon](https://img.shields.io/badge/PayPal_AI_Hackathon-2026-003087?style=for-the-badge)](https://paypalaihackathon.devpost.com/)
[![Built with APIMatic](https://img.shields.io/badge/APIMatic-Context_Plugin-10A37F?style=for-the-badge)](#)
[![Powered by AG Grid](https://img.shields.io/badge/AG_Grid-Enterprise-FF4081?style=for-the-badge)](#)

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

**Prerequisites:** Docker, Node.js 20+, and a PayPal Sandbox Business Account.

1. **Clone & Configure**
   ```bash
   git clone https://github.com/your-org/driftguard.git
   cd driftguard
   cp .env.example .env
   # Add your PayPal Sandbox Client ID, Secret, and Anthropic API key
   ```

2. **Boot the Harness**
   ```bash
   make up
   ```
   *This spins up the Postgres database, the mitmproxy interceptor, the orchestrator worker, and the AG Grid dashboard.*

3. **Run a Chaos Suite Against a Target**
   ```bash
   # Using the DriftGuard CLI
   driftguard run ./path/to/target/ai-agent-repo
   ```

4. **View the Ledger**
   Open `http://localhost:3000` to watch the live AG Grid telemetry matrix as DriftGuard drops packets, checks PayPal's ledger, and turns red rows green.

## Repository Structure
* `/engine` - The MITM proxy, deterministic reconciler, and API orchestrator.
* `/ai` - Tree-sitter AST scanner, scenario generator, and APIMatic fixer.
* `/dashboard` - The AG Grid command center and visual ledger.
* `/targets/demo-shop` - A deliberately vulnerable sandbox commerce app seeded with 10 exact bugs to test the harness.
* `/contracts` - Shared Pydantic schemas validating the JSON pipeline between the AI and the execution engine.

## Contributors

Team Pixentropy 

- [Swastik Bose](https://github.com/VasuBhakt)
- [Kiran Patra](https://github.com/patrakiran)
- [Prathamesh Prasad](https://github.com/Prathamesh51-debug)
