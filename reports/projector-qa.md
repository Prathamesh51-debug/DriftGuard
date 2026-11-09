# Projector-size dashboard check — 9 November 2026

Tested the running Vite frontend against the live engine API and stored PayPal
Sandbox runs in Chromium. The advertised URL was `http://localhost:5173`.

| View | 1920×1080 | 125% presentation zoom (1536×864 CSS viewport) |
|---|---|---|
| Landing page | No horizontal overflow, four latest runs, FAIL→PASS terminal loop | — |
| Overview | Live run data; no page exception or overflow | — |
| Runs | Live data; no page exception or overflow | No overflow; verdict chips and rows readable |
| Faults | No page exception or overflow | — |
| Ask Studio | Live rows and chart; no page exception or overflow | No overflow; chart, AI pane and data pane visible |
| Docs | No page exception or overflow | — |
| Verified F4 run detail | — | No overflow; Fix tab shows PASS, exact patch SHA-256 and diff |

The 125% presentation view is the recommended projector setting. At native
1920×1080, the Runs and Studio table text is smaller. The check used fresh
browser contexts, so it did not depend on saved sidebar or theme settings.

Opening the frontend on `127.0.0.1:5173` originally triggered a CORS rejection
because the API only allowed `localhost:5173`. Both loopback origins are now
allowed; a second browser check confirmed real runs load from `127.0.0.1` too.
The first AG Studio load takes longer than the other views because its bundle
is about 5.46 MB before gzip; the build warns about its size. Screenshots and
machine-readable measurements remain in ignored `logs/verification/` locally.

This covers local Chromium presentation, not the hosted deployment or a
physical projector. The AG Studio AI reply itself requires the AI service and
was not sent a prompt as part of this visual check.
