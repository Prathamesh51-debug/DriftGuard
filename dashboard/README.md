# DriftGuard Dashboard

React + Vite + TypeScript command center. It shows every chaos run in an AG Grid matrix and opens an evidence drawer with the PayPal IDs behind each verdict.

## Run it

Start an API, then the dashboard (from the repo root unless noted):

```bash
# 1. API: the mock runner serves the contracts fixtures
pip install -r mock_runner/requirements.txt
uvicorn mock_runner.app:app --port 8000

# 2. Dashboard
cd dashboard
npm install
npm run dev        # http://localhost:5173
```

To point at the real engine instead, set `VITE_API_URL` (default `http://localhost:8000`).

## What's here

- `src/api.ts` is the API client (`GET /runs`, `POST /runs`, `POST /runs/{id}/rerun`).
- `src/types.ts` mirrors `contracts/models.py`. Keep them in sync.
- `src/components/RunsGrid.tsx` is the results matrix (AG Grid Community).
- `src/components/EvidenceDrawer.tsx` shows expected vs observed, PayPal IDs, and the scenario.
- `src/components/VerdictChip.tsx` is the PASS / FAIL / ERROR / RUNNING chip.

## Scripts

`npm run build` type-checks and builds. `npm run lint` runs Oxlint.
