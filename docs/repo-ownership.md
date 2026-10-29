# DriftGuard Repository Ownership Map

Who leads and who reviews every folder and file in the monorepo. Roles match the [Execution Planner](planner.md):

|  Role | Name         | Focus                                                 |
|:-----:|--------------|-------------------------------------------------------|
| **A** | Engine       | Proxy, orchestrator, reconciler, API, infra           |
| **B** | AI + Attacks | Scanner, contracts, scenarios, demo shop, README      |
| **C** | AI + Fixes   | Fixer, explainer, buyer driver, dashboard, CLI, video |

- **Leads** writes the code and owns the folder.
- **Reviews** is the backup reviewer who approves pull requests touching it.
- The review rotation holds throughout: A's PRs are reviewed by B, B's by C, C's by A.
- `contracts/` is the exception: changes need approval from all three roles (planner rule 3).

## Ownership Table

| Folder / File                         | What lives there                            | Leads | Reviews |
|---------------------------------------|---------------------------------------------|:-----:|:-------:|
| **`driftguard/`**                     | Monorepo root                               |   —   |    —    |
| `contracts/`                          | Scenario + Result schemas, fixtures         |   B   |   A, C  |
| `engine/`                             | API, orchestrator, reconciler, proxy addons |   A   |    B    |
| **`ai/`**                             | (group)                                     |   —   |    —    |
| `ai/common/`                          | LLM adapter, spend cap, cache               |   B   |    C    |
| `ai/scanner/`                         | tree-sitter + LLM flow map                  |   B   |    C    |
| `ai/scenario_gen/`                    | Scenario JSON, `expected_total`             |   B   |    C    |
| `ai/injection/`                       | F7 payload library                          |   B   |    C    |
| `ai/webhook_replayer/`                | F6 replay modes                             |   B   |    C    |
| `ai/explainer/`                       | Evidence-checked explanations               |   C   |    A    |
| `ai/fixer/`                           | Patch, rebuild, re-run (max 3)              |   C   |    A    |
| `ai/buyer_driver/`                    | Playwright sandbox approval                 |   C   |    A    |
| `mock_runner/`                        | Fixture API so the UI never waits           |   C   |    A    |
| `cli/`                                | `driftguard run` / `report`                 |   C   |    A    |
| `dashboard/`                          | React + Vite + TS + AG Studio               |   C   |    A    |
| **`targets/`**                        | (group)                                     |   —   |    —    |
| `targets/demo-shop/`                  | Express shop, 10 seeded bugs                |   B   |    C    |
| `targets/known-fixes/`                | Patches the fixer never reads               |   B   |    C    |
| **`evals/`**                          | (group)                                     |   —   |    —    |
| `evals/scanner/`                      | Precision / recall                          |   B   |    C    |
| `evals/verdict/`                      | Bugs caught, 0 false alarms                 |   A   |    B    |
| `evals/fixer/`                        | Fixes passing re-run                        |   C   |    A    |
| `evals/explainer/`                    | % needing no regeneration                   |   C   |    A    |
| `study/`                              | "X of 25" protocol (`raw/` stays private)   |   B   |    C    |
| `infra/`                              | Render, Docker + CA trust, scripts          |   A   |    B    |
| **`docs/`**                           | (group)                                     |   —   |    —    |
| `docs/architecture.md`                | Diagram + video slide                       |   C   |    A    |
| `docs/devpost.md`                     | A drafts, B verifies numbers                |   A   |    B    |
| `docs/decision-log.md`                | Append-only, everyone writes                |  ALL  |   ALL   |
| `docs/demo-script.md`, `docs/video/`  | Script, storyboard                          |   C   |    A    |
| `.github/`                            | CODEOWNERS, CI, PR template                 |   A   |    B    |
| `README.md`                           | Run guide from a clean clone                |   B   |    C    |
| `Makefile`, `compose`, `.env.example` | Build and local-run tooling                 |   A   |    B    |

## Ownership by Role

### A: Engine
- `engine/`
- `evals/verdict/`
- `infra/`
- `docs/devpost.md` (drafts; B verifies numbers)
- `.github/`
- `Makefile`, `compose`, `.env.example`

### B: AI + Attacks
- `contracts/`
- `ai/common/`, `ai/scanner/`, `ai/scenario_gen/`, `ai/injection/`, `ai/webhook_replayer/`
- `targets/demo-shop/`, `targets/known-fixes/`
- `evals/scanner/`
- `study/`
- `README.md`

### C: AI + Fixes
- `ai/explainer/`, `ai/fixer/`, `ai/buyer_driver/`
- `mock_runner/`, `cli/`, `dashboard/`
- `evals/fixer/`, `evals/explainer/`
- `docs/architecture.md`, `docs/demo-script.md`, `docs/video/`

### Everyone
- `docs/decision-log.md`: append-only, anyone may write, anyone may review.

## Quick Reference: Who Reviews Whom

| Author | Reviewer | Folders                                                                                                                                                                                  |
|:------:|:--------:|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|   A    |    B     | `engine/`, `evals/verdict/`, `infra/`, `docs/devpost.md`, `.github/`, `Makefile` + `compose` + `.env.example`                                                                            |
|   B    |    C     | `ai/common/`, `ai/scanner/`, `ai/scenario_gen/`, `ai/injection/`, `ai/webhook_replayer/`, `targets/*`, `evals/scanner/`, `study/`, `README.md`                                           |
|   B    |   A, C   | `contracts/`                                                                                                                                                                             |
|   C    |    A     | `ai/explainer/`, `ai/fixer/`, `ai/buyer_driver/`, `mock_runner/`, `cli/`, `dashboard/`, `evals/fixer/`, `evals/explainer/`, `docs/architecture.md`, `docs/demo-script.md`, `docs/video/` |
|  ALL   |   ALL    | `docs/decision-log.md`                                                                                                                                                                   |
