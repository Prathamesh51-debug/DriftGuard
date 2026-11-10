# DriftGuard

A payment can succeed even when the app never receives the success response. DriftGuard tests what a shop does next: does it retry, mark the order paid, or check what PayPal actually recorded?

The project runs deliberately broken checkouts against **PayPal Sandbox**. A proxy introduces a fault, the runner drives a buyer through checkout, and the reconciler compares PayPal's order with the demo shop's state. The dashboard shows the result. A fixer can apply a patch to a temporary copy of the shop and run a new Sandbox order to see whether the fault still fails.

Built by Team Pixentropy for the PayPal AI Hackathon.

## What has been proved

| Fault | Seeded failure | Saved patched rerun |
|---|---|---|
| F1 · lost capture response | PayPal captured; shop missed the record | PASS: one capture on both sides |
| F2 · simulated gateway timeout | Retry produced two PayPal orders | PASS: one order, one capture |
| F3 · declined instrument | Shop recorded a capture PayPal declined | PASS: neither side recorded a capture |
| F4 · invoice response fault | Shop lost the capture record | PASS: one capture on both sides |

These are **four local runs of curated patches against new Sandbox orders**, one patched rerun per fault. [The saved evaluation](evals/fixer/results/live-fixer-eval.md) has the parent and child run IDs, observations, patch hashes, and limits. It does not establish a general model success rate. F4 uses a simulated invoice response failure in the proxy; it does not reproduce PayPal's real duplicate-invoice error.

F5–F7 have seeded shop behaviors and contract fixtures. They still need fresh live Sandbox red-to-green evidence. In F6, replaying a webhook can make the shop process an event twice; **it does not create a second PayPal capture**. F7 records a simulated refund in shop state; **it does not call PayPal's refund API**.

## Try it

You need Python, Node.js/npm, Docker Desktop, PayPal Sandbox REST credentials, and a Sandbox buyer account. The buyer driver also needs Playwright Chromium. Copy `.env.example` to `.env`, fill in the PayPal credentials and buyer login, and keep `.env` private.

From the repository root:

```powershell
python -m pip install -r engine/requirements.txt
python -m pip install -r ai/fixer/requirements.txt
python -m playwright install chromium
npm install --prefix targets/demo-shop
npm install --prefix dashboard
docker compose up -d
```

Start each of these in its own terminal:

```powershell
python -m uvicorn engine.api.main:app --port 8000 --reload
python -m uvicorn ai.service.app:app --port 8001 --reload
npm --prefix targets/demo-shop run dev
npm --prefix dashboard run dev
```

Open `http://localhost:5173/` for the landing page and `http://localhost:5173/live` for stored runs. Run `python -m cli run F1` from another terminal, then open its result in the dashboard. `python -m cli report --all` lists stored runs. A FAIL returns exit code 1 because the test found the seeded bug; ERROR returns 2 because the run could not be completed.

The dashboard uses `http://localhost:8000` by default. Set `VITE_API_URL` in `dashboard/.env.local` if your API is elsewhere. Studio's model endpoint defaults to port 8001; without the AI service or a valid Anthropic key, model answers are unavailable. The run table and reconciler work without a model key.

For a local patch-and-rerun demo, set `DRIFTGUARD_ENABLE_FIX_RERUN=1` and `DRIFTGUARD_LLM=none` in `.env` **before** starting the API. Use **Generate and verify fix** on a failed run. The engine applies its curated patch to a disposable shop copy, builds it, runs a new order, and stores a child result. This executes patched Node code, so use it only on a trusted local machine. It is disabled on the public preview.

If port 8080 is already in use, stop the other service or change the proxy mapping and matching proxy configuration. If PostgreSQL is unavailable, the engine falls back to persistent SQLite and prints that choice at startup. A working database alone does not start the shop, proxy, or buyer browser.

## Hosted preview

The Render blueprint serves the React dashboard and a **fixture-backed API**. It lets visitors inspect example F1–F7 runs and prepared before/after outcomes. Its launch and verify buttons do **not** drive Playwright, run mitmproxy, apply code, or make a new PayPal Sandbox payment. Sample responses carry `mode: "sample"` for the UI. To see a live checkout, use the local setup above and the [saved evidence](evals/fixer/results/live-fixer-eval.md).

Hosted Studio can optionally call Anthropic from the API service. Set `ANTHROPIC_API_KEY` only as a Render secret, after setting a spend cap in the Anthropic Console. Without the key it gives a labeled prepared answer. The in-process call limits reset when the service restarts; they are not a billing limit. Never put an API key in a `VITE_` variable.

## How it fits together

```text
PayPal Sandbox ←→ mitmproxy ←→ seeded demo shop
                              ↑          ↓
                       buyer driver   shop state
                              ↓          ↓
                        runner → reconciler → stored run → dashboard
                                      ↑
                          fixer: temporary shop copy + new run
```

- `engine/`: API, run orchestration, proxy rules, and deterministic reconciliation.
- `targets/demo-shop/`: the intentionally vulnerable TypeScript shop. `targets/known-fixes/` holds curated repair patches.
- `ai/`: buyer automation, a pattern-based source scanner, scenario generation, explainer, and patch fixer. Model output proposes changes; the engine decides the verdict.
- `contracts/`: schemas and example scenarios/results. Fixtures are examples, not evidence of a live payment.
- `dashboard/`: React and AG Grid interface, with an AG Studio canvas.
- `mock_runner/`: the fixture API used only for the hosted preview.
- `evals/`: tests and saved evaluations. The [study folder](study/methodology.md) contains an exploratory annotation dataset, not a reproducible 25-repository Sandbox study.

The current scanner uses source patterns, not Tree-sitter. The live path uses PayPal Orders create/capture and order evidence; F7 refunds and parts of F4/F6 are shop/proxy simulations. The proxy's active fault is shared, so run faults sequentially. These limits matter if you adapt the harness to another shop.

## Team

- [Swastik Bose](https://github.com/VasuBhakt) · engine and reconciliation
- [Kiran Patra](https://github.com/patrakiran) · scenarios and demo shop
- [Prathamesh Prasad](https://github.com/Prathamesh51-debug) · fixer, dashboard, and buyer driver

See [repo ownership](docs/repo-ownership.md) for the folder map and [the original planner](docs/planner.md) for the hackathon plan. The planner records intended work; this README describes current behavior.
