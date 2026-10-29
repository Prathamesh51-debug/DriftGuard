# DRIFTGUARD TEAM EXECUTION PLANNER 

PayPal AI Hackathon 2026 | Revised Edition: Oct 27 (IST) | Code freeze: Nov 10 | Submit: Nov 12 

This planner turns the DriftGuard build plan into a daily schedule with a named owner for every task. It incorporates the re-balanced role assignments to protect the critical path. The golden rule remains: AI proposes, code decides. 

## Part 1: The Mission, The Rules, The Loop 

Goal: Prove, against PayPal's own records, that an AI payment app is safe to ship, and show it fixing itself when it is not. 

### The Core Team 

|Role|Owns|Backup Reviewer|
|---|---|---|
|A: Engine|Proxy, Docker sandbox, orchestrator, reconciler, API, Render deploy,<br>Devpost draft|Reviewed by B|
|B: AI + Attacks|Scanner, contracts/schemas, F7 attacks, demo shop, webhook replayer,<br>README, Devpost sign-off|Reviewed by C|
|C: AI + Fixes|Buyer driver, explainer, fixer, dashboard/Studio agent, mock runner, CLI,<br>video lead|Reviewed by A|



### The Re-Run Loop 

|1. Scan (B)|2. Attack (B)|3. Run (A)|4. Reconcile (A)|5. Explain + Fix<br>(C)|6. Re-run (A)|
|---|---|---|---|---|---|
|Map every PayPal|Write fault|Proxy injects|Read PayPal|Evidence and|Red must turn|
|call|scenarios|faults|records|patch|green|



### Seven Working Rules 

1. AI proposes, code decides. A model output never decides pass or fail, never computes an expected amount, never accepts a fix. Any pull request that breaks this is rejected. 

2. Every verdict traces to PayPal IDs. Order IDs, capture IDs, refund IDs and proxy log references sit in the Result. 

3. Contracts first. Scenario and Result JSON are agreed on Day 1. Changes need a pull request with all three approvals. 

4. Done means: merged, runs from the README, has a test or eval, visible in the dashboard. 

5. Vertical slice before breadth. F1 works end to end on the demo shop before F2 to F7 start. 

6. Blocked for >2 hours? Say so in chat. Silence is the most expensive bug. 

7. Freeze on 10 Nov. After that: bug fixes only, no new features. 

Critical Update: Task loads have been rebalanced to move non-critical integrations (Mock Runner, CLI, F7 E2E, README) off Role A, safeguarding the proxy/reconciler pipeline. 

DriftGuard Execution Planner 

Page 1 

Part 2: Who Owns What (Rebalanced) 

|Component|Lead|Supports/Reviews|Final Due|
|---|---|---|---|
|Contracts:Scenario + Result JSON, schemas,<br>fixtures|B|A chairs session, C co-signs|Frozen 2 Nov|
|Mock runner(fake results so B and C never<br>wait)|C|A advises contract|Replaced 31 Oct|
|Fault-injection proxy(mitmproxy addons) F1 to<br>F4|A|B writes payloads|6 Nov|
|Docker sandbox, hosts override, CA trust|A|B (demo shop Dockerfile)|5 Nov|
|Orchestrator, Postgres, SKIP LOCKED queue|A|C (calls buyer driver)|7 Nov|
|Reconciler(reads PayPal records, decides<br>verdict)|A|B on F5 money check|6 Nov|
|API & Re-run endpoint|A|C consumes|4 Nov|
|CLI(driftguard run)|C|A exposes API|8 Nov|
|Render deploy, integration lead|A|C depends on URL|9 Nov|
|Demo shopwith 10 seeded, labelled bugs|B|A, C consult on targets|5 Nov|
|Scanner(tree-sitter + LLM flow map)|B|C reads flow maps|7 Nov (evals)|
|Scenario generator, injection library|B|A runs them|5 Nov|
|Webhook replayerF6, money-math F5|B|A on F5 reconciler rule|6 Nov|
|F7 Prompt Injection E2E(Shop assistant,<br>payloads, run)|B|A keeps no-refund check|6 Nov|
|Public repo study(the "X of 25" number)|B|A, C double-check|7 Nov|
|Buyer driver(Playwright approval)|C|A calls it|30 Oct (module)|
|Fixer+ APIMatic context + re-run loop|C|A API, B bug labels|6 Nov|
|Dashboard, Studio agent, Explainer, Video|C|A API, B scenarios|11 Nov|
|README run guide|B|A reviews|9 Nov|
|Devpost Text|A(Draft)|B(Verify & Sign-off)|11 Nov|



### Review Rotation & Backup Triggers 

Every pull request gets a review within 4 hours: A’s PRs by B; B’s by C; C’s by A. This ensures cross-training. If slips occur, pre-agreed triggers activate automatically: 

1. If Reconciler v0 is not done by Fri 30 Oct: B takes F2 to F4 reconciler rules (B already owns expected-total). 

2. If A is behind on Wed 4 Nov: C takes ownership of the Render blueprint. 

DriftGuard Execution Planner 

Page 2 

## Part 3: Shared Setup Checklist (Tue 27 Oct) 

|Task|Owner|
|---|---|
|Create PayPal dev account, sandbox Business/Personal accounts, REST app. Save secrets inlocal.env.|A|
|Create GitHub repo (private), protect main, add.env.example, add secrets scan in CI.|A|
|Claim Render credits ($50) and create account; no deploy yet.|A|
|Create shared task board (GitHub Projects): Backlog, Doing, Review, Done. Add phase gates.|A|
|Create Claude API key, set spend cap, write thin LLM adapter (Sonnet for code, Haiku for labels, caching).|B|
|Confirm Devpost team page lists all members; read rules page for submission requirements.|B|
|Sign up for AG Studio (trial ends 15 Dec). Plan deployment key generation for 3-5 Nov.|C|
|Get access to APIMatic Context Plugin (MCP server); confirm launch process.|C|
|Pick daily sync time (15 min) and team chat. Put gates in calendars.|All|
|Hold 60-minute contracts session. Output:contracts v0.1tagged by midnight.|All|



## Part 4: The Calendar at a Glance 

|Phase|Dates|Build Focus|Gate (Done When)|
|---|---|---|---|
|0: Spikes|Tue 27 – Wed 28 Oct|Go/no-go tests, contracts v0.1,<br>mock runner, demo shop|Night of 28 Oct: All spikes pass or<br>fallbacks applied.|
|1: Vertical|Thu 29 Oct – Mon 2 Nov|F1 end to end on demo shop.<br>Integration evening Mon 2 Nov.|First red result with PayPal IDs, no<br>manual steps.|
|2: Breadth|Tue 3 – Fri 6 Nov|F2-F7, fixer, dashboard, deploy.<br>Integration evening Fri 6 Nov.|Seeded bugs caught, 3+ fixed and<br>proven green.|
|3: Harden|Sat 7 – Mon 9 Nov|Timeouts, idempotency, CLI,<br>README, evals, video, text.|A stranger can run it from the<br>README.|
|4: Freeze|Tue 10 – Thu 12 Nov|Bug fixes only, final video upload,<br>submit.|Submitted on 12 Nov in IST<br>daytime.|



### Fixed Dates & Milestones 

|Date|Event|Who|
|---|---|---|
|Wed 28 Oct, 21:00|Go/no-go. Fill spike table. Apply fallbacks if needed.|All|
|Mon 2 Nov, evening|Integration evening 1. Merge, run E2E, record 60s backup video.|All (A leads)|
|Wed 4 Nov|Re-run API endpoint delivered to C. AG deploy key window opens.|A, C|
|Thu 5 Nov|Re-check public hackathon entries for similar tools.|B|
|Fri 6 Nov, evening|Integration evening 2. All 7 faults on demo shop, 3+ fixes green.|All (A leads)|
|Mon 9 Nov|Stranger test of README on clean machine.|All|
|Tue 10 Nov|CODE FREEZE. Tag RC. Re-check entries.|A tags, B<br>checks|
|Th<br>12 N<br>14 00|S b<br>i<br>C<br>fi<br>b<br>i<br>i<br>h<br>l|B<br>b<br>i|



DriftGuard Execution Planner 

Page 3 

## Part 5: Phase 0 (Spikes and Contracts) 

|Day|Role A (Engine)|Role B (AI + Attacks)|Role C (AI + Fixes)|
|---|---|---|---|
|Tue 27<br>Oct|• Sandbox accounts & REST app.<br>• Repo skeleton.<br>• Lead contracts session.<br>• Start Spike 1 (mock response<br>capture error).|•Own contracts/package<br>creation.<br>• Build LLM adapter (spend<br>cap/cache).<br>• Scaffold demo shop<br>(Express/Vite).<br>• Start Spike 4 (public repo<br>queries).|• Co-sign contracts.<br>• AG Studio & APIMatic sign up.<br>• Start Spike 3 (headless Playwright<br>approval link).|
||Gate:By midnight contracts|v0.1 tagged, Spike 1 has an answer, sa|ndbox login works.|
|Wed 28<br>Oct|• Finish Spike 1.<br>• Spike 2: SDK script in Docker<br>(hosts override + CA trust).<br>• Write Spike 2 gotchas.|• Finish Spike 4 (scanner over 5<br>repos).<br>• Deliver demo shop v0 to A & C.<br>• Draftbugs.yaml: 10 seeded<br>bugs.|• Finish Spike 3: headless<br>Playwright (90% pass rate).<br>• Spike 5: APIMatic MCP client test.<br>•Deliver Mock Runner to unblock<br>UI.|



### The 6 Go/No-Go Spikes (Wed 28 Oct, 21:00) 

|#|Own|Steps|Pass When|If it Fails (Fallback)|Status|
|---|---|---|---|---|
|1|A|Create order. Approve manually. Capture withPayPal-<br>Mock-Response: {"mock_application_codes":<br>"INSTRUMENT_DECLINED"}. Verify endpoints behavior.|Sandbox<br>returns mocked<br>error on<br>capture.|Drop F3/F4 as PayPal<br>errors; keep proxy-made<br>errors only.|✅ **PASSED (29 Oct)**<br>HTTP 422 INSTRUMENT_DECLINED verified|
|2|A|Docker mitmproxy reverse mode. Target resolves via<br>extra_hosts/network alias. Inject CA trust. Run SDK script.|Calls appear in<br>proxy log; app<br>still works.|Base-URL override targets<br>only; list in README.|✅ **PASSED (29 Oct)**<br>Reverse proxy intercepts & logs flows|
|3|C|Script creates order. Playwright logs in as sandbox buyer,<br>consents, waits for return URL. API captures. Run 10x.|Approved &<br>captured with<br>no human.|Pre-approve orders for<br>video/demo; live buyer stays<br>manual.|✅ **PASSED (29 Oct)**<br>10/10 headless approve + capture, ~12s per run|
|4|B|Write tree-sitter queries for 5 repos. Run, hand-label true<br>sites, record found/missed.|Finds sites in 4<br>of 5 repos.|Narrow scanner to<br>TypeScript only.|Pending|
|5|C|Launch APIMatic MCP. Ask for "capture order idempotency"<br>in TS. Check against SDK typings.|Fixer gets<br>correct SDK<br>usage.|Build curated patch<br>templates in IDE manually.|Pending|
|6|A|Can hosted worker run target + proxy?|Confirmed yes.|Run as processes in worker,<br>or small VM, or replay demo<br>mode.|Pending|



DriftGuard Execution Planner 

Page 4 

Part 6: Phase 1 (Vertical Slice - F1 End to End) 

|Day|Role A (Engine)|Role B (AI + Attacks)|Role C (AI + Fixes)|
|---|---|---|---|
|Thu 29<br>Oct|• Proxy v1 (mitmproxy reverse).<br>• Log JSONL (ID, hash).<br>• Actiondrop_response(F1).<br>• Spike 6 decision on hosting.|• Scanner v0 (TypeScript).<br>• Demo shop full checkout + BUG-<br>01.<br>• Scenario validator in code + tests.|• Buyer driver module.<br>• Dashboard: results matrix, run<br>launcher.<br>• Explainer prompt design on F1<br>mock.|
||Gate:Proxy log sh|ows dropped-response capture on demo|shop.|
|Fri 30 Oct|• Reconciler v0 (F1 rule).<br>• Harvest order IDs from proxy.<br>• Postgres tables & orchestrator<br>SKIP LOCKED queue.<br>• Real API replaces mock runner.|• Scenario generator v0 (Claude<br>proposes, code validates).<br>• Deliver first valid F1 Scenario<br>JSON to A.|• Deliver buyer driver to A.<br>• Explainer v0 (JSON in/out, strict<br>code checks).<br>• Dashboard switches to real API.|
||Gate:A runs F1 ma|nually; buyer driver callable from orche|strator.|
|Sat 31<br>Oct|• Orchestrator state machine.<br>• Step timeouts; safe retry.<br>• First red result on demo shop.|• Scanner-to-scenario pipeline.<br>• Scanner test: demo shop sites<br>found.<br>• Add BUG-02.|• Fixer v0: Failing result in, diff out.<br>• Apply patch to copy (never<br>original).<br>• Dashboard detail page (IDs,<br>impact).|
||Gate:First|red result with PayPal IDs on screen.||
|Sun 1<br>Nov|• Run F1 10x; fix flakiness.<br>• Writemake e2e.<br>• Pre-integration checklist.|• Validate flow map/Scenarios.<br>• Prepare integration branch.|• Human review of first fixer diff.<br>• Dashboard polish.|
|Mon 2<br>Nov|• Finishmake e2e.<br>• Lead evening merge & E2E run.|• Fix scanner bugs.<br>• Freeze contracts at v1.0.|• Explainer on real result.<br>• Fixer drafts patch.|
|Integration|• Log integration bugs.||• Record 60s backup video.|



Gate: First red result, no manual steps. Short integration bug list generated. 

DriftGuard Execution Planner 

Page 5 

Part 7: Phase 2 (Breadth - F2 to F7) 

|Day|Role A (Engine)|Role B (AI + Attacks)|Role C (AI + Fixes)|
|---|---|---|---|
|Tue 3 Nov|• F2 proxy delay.<br>• F3/F4 headers.<br>• Reconciler rules F2-F4.|• Scenario generator for F2-F4.<br>• Seed BUG-03 & 04.<br>• Add/driftguard/stateto<br>shop.|• Fix-and-rerun skeleton (rebuild,<br>re-run, check verdict).<br>• Explainer handles F2-F4.|
||Gate|:F1 to F4 all red on demo shop.||
|Wed 4<br>Nov|• Re-run endpoint (POST) to C.|• Injection library v1 (20-30<br>payloads).<br>• AI shop assistant variant (BUG-<br>10).<br>•F7 mechanics & E2E execution.<br>• Start webhook replayer.|• Before/after view (red to green).<br>• Generate AG Studio key (store<br>secret).<br>• Studio agent skeleton.|
||Gate:C re-r|uns via API. AG deployment key stored.||
|Thu 5<br>Nov|• Render blueprint (web, worker,<br>Postgres).<br>• Run F1 from hosted dashboard.|• F6 replayer (duplicate, unsigned).<br>• F5 math scenarios (totals in<br>code).<br>• Seed BUG-05 to 09.<br>• Repo study: build 25 app list.|• Fixer runs on BUG-01, 03, 09.<br>• Studio agent answers "why<br>failed?" from stored results.|
||Gate:Hos|ted URL runs F1 scenario end to end.||
|Fri 6 Nov<br>Integration|• F5 reconciler check.<br>• Hosted worker stability.<br>• Lead evening 7-fault run.|• Repo study pass 1 (static).<br>• Check every seeded bug is<br>caught.|• Before/after view with 3 fixes.<br>•CLI Skeleton.<br>• Run fixer on 3 bugs live for video<br>clips.|



Gate: Seeded bugs caught; 3+ fixed/green. First study numbers exist. 

DriftGuard Execution Planner 

Page 6 

Part 8: Phases 3 & 4 (Harden, Freeze, Submit) 

|Day|Role A (Engine)|Role B (AI + Attacks)|Role C (AI + Fixes)|
|---|---|---|---|
|Sat 7<br>Nov|• Hardening: step timeouts,<br>idempotent workers.<br>• Crash-resume test.|• Scanner eval report.<br>• Repo study final run/anonymize.|• Dashboard polish.<br>• Fixer eval table.<br>• Video script v1.|
||Gate:Wor|ker crash test passes; eval tables exist.||
|Sun 8<br>Nov|• Review README.|•Write README run guide(clean<br>clone, Compose up).<br>• Verify text numbers.|•CLI(driftguard run / report).<br>• Video storyboard & first takes.<br>• Arch slide for video.|
||Gate:READM|E exists, written from clean checkout by|B.|
|Mon 9<br>Nov|• Hosted site smoke test on fresh<br>DB.<br>•Draft Devpost Textfrom B's<br>notes.|• Stranger test supervision.<br>• Fix scanner/scenario breaks.<br>• Verify Devpost text numbers.|• Video take 1 complete.<br>• Dashboard works at projector<br>scale.|
||Gate:Stran|ger runs app successfully from README|.|
|Tue 10<br>Nov<br>FREEZE|•Tag Release Candidate.<br>• Final deploy from tag.<br>• Bug fixes only.|• Re-check rivals for similar tools.<br>• Sign-off Devpost text.|• Final video edit.<br>• Pre-approve orders as backup.|
||Gate:Tag exis|ts. New work needs written reason in ch|at.|
|Wed 11<br>Nov|• Smoke test 3x.<br>• Secrets scan.<br>• Repo public (if rules require).|• Devpost form draft.<br>• Check "X of 25" statement.|• Upload video, check captions.<br>• Two full live rehearsals.|
|Thu 12<br>Nov|• Verify links from private window.<br>• On-call for fixes.|•Submit by 14:00 IST.<br>• Re-read live page.|• Check video plays from<br>submission page.|
|SUBMIT|||• Post final demo script.|



DriftGuard Execution Planner 

Page 7 

## Part 9: Role Playbooks (A & B) 

### Role A | Engine (The Critical Path) 

Make faults happen reliably, ensure correct verdicts, and orchestrate the loop. (Load strictly protected). 

- A1 Repo, CI & Orchestrator: Monorepo structure, Docker Compose. Postgres SKIP LOCKED queue. Kill-worker crash resilience ensures no duplicate PayPal harness orders. 

- A2 Fault-injection Proxy (F1-F4): mitmproxy reverse mode. Addons read Scenario inject blocks. Never resolve PayPal hostname to proxy internally. Log PayPal-Request-Id. 

- A3 Reconciler: OAuth token, get order, list captures. Decimal math. Verdicts map to PayPal IDs. Output Result JSON. (F7 checks for no-refund/payout). 

- A4 API & Deploy: FastAPI endpoints (/runs, /rerun). Render blueprint. Live integration lead. 

- A5 Devpost Draft: Draft the narrative using B's study notes, letting B handle the final mathematical sign-off. 

### Role B | AI Analysis & Attacks 

Find where apps lose money, write attacks, and manage schemas & public claims. (AI proposes, code computes). 

- B1 Contracts & Schemas: Own the contracts/package Pydantic models. Export JSON Schema for CI. 

- B2 Demo Shop: Express + SDK checkout. 10 seeded // BUG-NN bugs. Add /_driftguard/state for readonly assertions. 

- B3 Scanner (Tree-sitter + LLM): Query call sites (TypeScript/JS). Output flow map. LLM only links flows; code verifies lines. 

- B4 Scenario Generator: Maps faults to flows. Claude proposes names; code handles expected_total Decimal math. 

- B5 F7 Prompt Injection E2E: Own the shop assistant, injection payloads (overrides, markdown hacks), and run the F7 end-to-end execution. 

- B6 Webhook Replayer (F6): Capture and replay real sandbox events (duplicate, tampered, out-of-order). 

- B7 README & Repo Study: Write the run guide from a clean clone. Execute the 25-repo study, anonymize, compute precision/recall evals. Sign off Devpost facts. 

DriftGuard Execution Planner 

Page 8 

## Part 9: Role Playbooks (C) & Part 10: Fault Matrix 

### Role C | AI Fixes & Insights 

Turn red results into explanations, fix code via LLM, and build the UI layer. 

- C1 Mock Runner & CLI: Build the fixture server to unblock UI on Day 2. Build the driftguard run CLI wrapper. 

- C2 Buyer Driver: Playwright module to click through PayPal sandbox approval headless. Return ApprovalResult. 

- C3 Dashboard (AG Studio): React+Vite matrix. Custom AG widgets (verdict chip, evidence drawer). Secure AG deployment key early. 

- C4 Explainer: Haiku+Sonnet to explain traces. Strict rule: code verifies every number/ID in output exists in the Result. 

- C5 Fixer & Re-run: APIMatic Context Plugin provides SDK typings. Model drafts diff. Apply to copy, rebuild, call A's re-run API. Max 3 attempts. 

- C6 Video Lead: Storyboard, record at 1080p, final 3-minute cut. Pre-approve orders for safe recording. 

### The Seven Faults & Seeded Bugs 

|Fault|Trigger|Safe Means<br>(Code)|Seeded Bug|Typical Fix|
|---|---|---|---|---|
|F1 Lost Capture|Drop reply after 201|1 capture per<br>purchase|BUG-01|SendPayPal-Request-Id;<br>check status on retry|
|F2 Slow PayPal|Delay past app<br>timeout|No duplicate<br>order|BUG-02|Idempotent create; status check|
|F3 Decline|Mock DECLINED|Order never<br>paid|BUG-03|Handle 422; keep unpaid|
|F4 Dup Invoice|Mock DUPLICATE|Error surfaced|BUG-04|Deterministicinvoice_idper cart|
|F5 Money Math|Discounts, tax, 0-dec|Amount ==<br>expected|BUG-05, 06, 07|Integer/Decimal minor units|
|F6 Webhooks|Replay, unsigned,<br>modded|Rejected or 1x<br>effect|BUG-08, 09|Verify signature; dedupe ID|
|F7 Prompt Inj.|"Refund $500" via<br>chat|No refund in<br>records|BUG-10|Enforce policy in code; remove tool|



DriftGuard Execution Planner 

Page 9 

## Part 10 (cont.): Hand-offs, Evals, and Repo Study 

### Critical Hand-off Schedule 

|Due|From|To|What|Acceptance|
|---|---|---|---|---|
|27 Oct|B|All|Contracts v0.1|Load fixtures cleanly|
|28 Oct|B|A, C|Demo shop v0|Proxy sees calls; C approves|
|28 Oct|C|A, B|Mock runner|Dashboard renders output|
|30 Oct|B|A|F1 Scenario JSON|A runs with no edits|
|30 Oct|C|A|Buyer driver|Orchestrator approves headless|
|31 Oct|A|C|Real API|Dashboard shows PayPal IDs|
|4 Nov|A|C|Re-run endpoint|C triggers re-run & gets verdict|
|6 Nov|B|A|F5 rule, F6 replayer|Rules call them; tests pass|
|8 Nov|B, C|All|README (B) & CLI (C)|Stranger test passes|



### Public Repo Study ("X of 25") Protocol 

Method: Select 25 public hackathon repos using PayPal. Run scanner. Tier 1: Manually review findings for doublecharge risks (no idempotency, blind retries). Tier 2: Run F1 via Docker on eligible apps. Report both static and dynamic numbers honestly ("X of 25 showed risk; Y reproduced"). 

Rules: Public code/sandbox only. No real names. Verify Devpost claims match these exact numbers. 

### Required Evals 

|Eval|Owner|Reported As|
|---|---|---|
|Scanner|B|Precision/recall on 10 seeded + 5 real repos (file/line auto-checked).|
|Verdict Math|A|Seeded bugs caught / total; false alarms on fixed versions = 0.|
|Fixer|C|Fixes passing re-run / attempted; time per fix.|
|Explainer|C|% needing no LLM regeneration (strict code checks passed).|



DriftGuard Execution Planner 

Page 10 

## Part 11: The 3-Minute Video & Submission 

### Video Timeline (C Leads) 

|Time|Beat|On Screen|Prep|
|---|---|---|---|
|0:00|The harm is real money. Buyer pays once;<br>sandbox shows two captures.|Sandbox record (2 captures), buyer view.|C records, B writes|
|0:20|Measured impact: "X of 25 apps double-<br>charge."|Clean number with method footnote.|B|
|0:45|AI reads code. Paste repo, map appears.|Dashboard launcher, flow map.|B scan, C screen|
|1:20|Deep PayPal use. Faults fire, matrix goes<br>red.|Matrix with IDs, proxy log snippet.|A engine, C UI|
|2:00|AI fixes, PayPal proves (Red to Green).|Before/after view, patch diff.|C|
|2:35|Credible architecture & close line.|Arch diagram, final tagline.|C, A reviews|



Close line: "Your AI agent says it charged once. DriftGuard checks PayPal's own records and proves it." 

### Submission Checklist 

- Title & Copy (A drafts, B finalizes): Problem, solution, stack, learnings. 

- Tags: Orders v2, Payments v2, Webhooks, mitmproxy, FastAPI, PostgreSQL, Claude, tree-sitter, APIMatic, React, AG Studio, Playwright. Sponsor prizes selected (APIMatic, AG Grid). 

- "X of 25" Claim: Verify against B's study notes. Include methodology paragraph. 

- Repo (A): Public link, README stranger test passed, secrets scan clean. 

- Demo (A): Live URL works in private window. 

- Video (C): Under 3:00, public, captions on, thumbnails uploaded. 

- Final Verification: Two people verify live submission page. Submit by 14:00 IST Thu 12 Nov. 

DriftGuard Execution Planner 

Page 11 

## Part 12: Risks, Fallbacks, and Cut List 

### Risk Matrix 

|Risk|Impact|Mitigation / Fallback|Own|
|---|---|---|---|
|Approval page blocks<br>automation|Runs need human|Selectors in 1 file; pre-approve orders for video.|C|
|CA trust fails for apps|Cannot see traffic|Base-URL override path; list supported targets.|A|
|Hosted worker container<br>block|Live runs fail|Spike 6 decision; fallback to VM or demo replay.|A|
|LLM invents findings|Lose trust|Strict code validation of file/line; discard bad JSON.|B|
|AG Studio trial ends early|Dashboard breaks|Request sponsor extension; static export backup.|C|
|API rate limits / outages|Pipeline stalls|Response caching; recorded fixtures for tests.|B/A|



### The Cut List (Drop in order if behind) 

Decide cuts at the 15-minute daily sync. Never move the freeze date. 

|Order|Trigger|Cut|
|---|---|---|
|Never Cut|Protected|F1 E2E, reconciler with IDs, red-to-green loop, matrix, video.|
|1|Behind Fri 6 Nov|Studio agent chat (keep dashboard matrix).|
|2|Behind Thu 5 Nov|F2 separate scenario (fold delay into F1 test).|
|3|Spike 4 weak|Python scanning (keep JS/TS).|
|4|Behind Thu 5 Nov|Dynamic repo study (report static numbers only).|
|5|Behind Fri 6 Nov|F6 tampered/out-of-order (keep duplicate/unsigned).|
|6|Behind Fri 6 Nov|F7 breadth (narrow to 5 payloads on 1 seeded bug).|
|7|Behind Sun 8 Nov|CLI polish (keep hosted dashboard + README).|



### Daily 15-Minute Sync Template 

1. Yesterday: What shipped (link). What did not & why. 

2. Today: The one thing due tonight. Who it unblocks. 

3. Blockers: Anything blocking >2 hours. Name the person to fix it. 

4. Gate Check: On track? If not, apply the cut list. 

DriftGuard Execution Planner 

Page 12 

