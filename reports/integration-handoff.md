# Integration handoff — 9 November 2026

## Role C proof completed locally

- F1–F4: four stored failed runs, four child reruns after curated patches, and four reconciled PASS results on distinct PayPal Sandbox orders. Exact run IDs and patch hashes are in [`live-fixer-eval.md`](../evals/fixer/results/live-fixer-eval.md).
- Direct Claude patch evidence exists for F2, F3, and F4. The product's four child reruns used curated fallback in offline mode; these are separate results.
- The Explainer's fresh Claude evaluation checked four stored Sandbox failures. Four of four passed the bounded numeric/ID verifier after a manual claim audit; see [`evals/explainer/results/README.md`](../evals/explainer/results/README.md).
- CLI, live dashboard routes, and projector-size layout were checked locally. See [`projector-qa.md`](projector-qa.md).

## Integration gates still open

| Gate | Owner in planner | Exact issue | Evidence needed to close |
|---|---|---|---|
| F5 money math | B shop/scenario; A runner/reconciler | The F5 scenario has `subtotal=35.99`, `tax_rate=0.0825`, `expect.amount=38.96`, but the runner sends both `amount=38.96` and `subtotal=35.99`. The shop selects `amount` first, then applies tax, so it tests the wrong base. Even if the runner selects the subtotal, the seeded `Math.floor((naiveTax - 0.04) * 100) / 100` yields 38.91, whereas the FAIL fixture says 38.92. | Align the scenario, runner and seeded calculation, then capture an original FAIL and patched PASS from distinct live Sandbox orders. |
| F4 invoice semantics | A proxy; B shop | The active proxy returns a synthetic `DUPLICATE_INVOICE_ID`-style response on capture when it sees a random numeric invoice. This proves an app-facing response failure and recovery, but does not prove an actual PayPal duplicate-invoice rejection. | Either retain the honest simulation label or create a real duplicate-invoice case and record PayPal's own error and the app's behavior. |
| F2 timing claim | A proxy; B scenario | The scenario fixture describes a 6000 ms delay, while the active proxy waits about 1000 ms before substituting 504. | Align timing or keep demo and explanation limited to the observed 1000 ms mechanism. |
| Hosted demo | A deployment | `infra/render.yaml` is a blueprint. The local proof has not established a working hosted API, proxy, shop, or Studio AI service. The local patch executor runs generated Node code and defaults off for public deployment. | Deploy an isolated environment, verify real run and Studio routes at the public URL, and design a secure executor before enabling public patch reruns. |

No F5 live verdict, real PayPal F4 duplicate-invoice rejection, or hosted demonstration is claimed here.
