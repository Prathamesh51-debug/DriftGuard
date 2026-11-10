# Who owns what

This map names the original area leads. It helps route reviews; it does not mean every commit in an area came from its lead. Check the commit author and diff for that. The [planner](planner.md) is the team's original schedule, while the [README](../README.md) describes current behavior.

| Area | Lead | What to review |
|---|---|---|
| `engine/`, `infra/`, Docker Compose | Swastik (A) | Proxy behavior, run lifecycle, PayPal reconciliation, deployment |
| `contracts/`, `targets/demo-shop/`, `ai/scanner/`, `ai/scenario_gen/`, `ai/injection/`, `ai/webhook_replayer/`, `study/` | Kiran (B) | Fault definitions, shop behavior, schema and fixture consistency |
| `ai/fixer/`, `ai/explainer/`, `ai/buyer_driver/`, `ai/service/`, `dashboard/`, `cli/`, `mock_runner/` | Prathamesh (C) | Patch safety, buyer automation, model behavior, frontend, hosted preview |
| `evals/` | Lead of the feature under test | Preserve raw evidence and distinguish source checks from live reruns |
| `README.md`, `docs/devpost.md`, `.env.example`, `render.yaml` | Shared | One accurate public story and runnable setup |

For a change spanning areas, ask the affected lead to review the boundary. In particular, a new fault crosses the demo shop, scenario contract, runner, reconciler, fixture, patch, and dashboard. A passing fixture test alone does not prove a live Sandbox outcome.

Do not commit Sandbox credentials, model keys, customer data, or generated payment logs. Keep `.env` local. The hosted preview uses fixtures; only the local engine and shop perform Sandbox runs.
