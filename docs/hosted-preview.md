# Hosted preview and Studio model

The Render blueprints (`render.yaml` and `infra/render.yaml`) deploy the dashboard with `mock_runner.app`. The hosted API reads F1–F7 contract fixtures. Launch and rerun actions show prepared sample outcomes; they do not run Playwright, mitmproxy, a patched shop, or a new PayPal Sandbox transaction. Sample run responses carry `mode: "sample"` so the dashboard can label them.

The hosted Studio can call Anthropic without putting the key in browser code:

1. Set `ANTHROPIC_API_KEY` as a secret on the **API web service** in Render. Never set a `VITE_` key or commit the value.
2. The blueprints set `DRIFTGUARD_PUBLIC_AI_ENABLED=1` and `ANTHROPIC_MODEL=claude-haiku-5-5`. The server ignores a model supplied by the browser and caps output at 2,048 tokens, input JSON at 40,000 characters, and tools at 20.
3. The server allows at most 30 model calls per client IP per hour and 100 total calls per process. These in-memory limits reset when Render restarts. **Set a [workspace or organization spend limit](https://platform.claude.com/docs/en/manage-claude/workspaces) in the Anthropic Console as the cost backstop.** Do not deploy the key until that limit is in place.
4. Without a key, Studio returns an answer labeled as a prepared preview. If a configured model call fails, Studio shows an error rather than silently substituting a canned answer.

The `POST /fix` route in the hosted preview returns a curated sample patch. The `POST /runs/{run_id}/verify-fix` route displays a prepared PASS fixture. Neither route checks or applies code in the hosted deployment. The saved local F1–F4 live Sandbox proof is in [`evals/fixer/results/live-fixer-eval.md`](../evals/fixer/results/live-fixer-eval.md).
