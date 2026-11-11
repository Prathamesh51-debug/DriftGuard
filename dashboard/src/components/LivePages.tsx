import { useEffect, useRef, useState } from 'react'
import type { FixState, Run } from '../types'
import { faultLabel, shortId, timeAgo } from '../format'
import { FAULT_CATALOG } from '../faultCatalog'
import { VerdictChip } from './VerdictChip'
import { FixPanel } from './FixPanel'

type PageProps = {
  runs: Run[]
  loading: boolean
  offline: boolean
  selectedId: string | null
  onSelect: (runId: string, opener?: HTMLElement) => void
}

function sortedRuns(runs: Run[]): Run[] {
  return [...runs].sort((a, b) => b.created_at - a.created_at)
}

function captureText(run: Run, app: boolean): string {
  const count = app ? run.result?.observed.app_recorded_captures : run.result?.observed.captures
  if (count == null) return 'No reading'
  return `${count} ${count === 1 ? 'capture' : 'captures'}`
}

function gapText(run: Run): string {
  if (!run.result) return '—'
  const appCaptures = run.result.observed.app_recorded_captures
  if (appCaptures == null) return 'No reading'
  if (appCaptures === run.result.observed.captures) return `0.00 ${run.scenario.expect.currency}`
  return run.result.money_impact || `${run.result.observed.amount_captured} ${run.scenario.expect.currency}`
}

function runSummary(run: Run): string {
  const result = run.result
  if (run.mode === 'sample') return `Sample: ${faultLabel(run.scenario.fault)} ${result?.verdict.toLowerCase() ?? 'running'}.`
  if (!result) return `${faultLabel(run.scenario.fault)} is still running.`
  if (result.verdict === 'ERROR') return 'This test could not complete.'

  const appCaptures = result.observed.app_recorded_captures
  const amount = result.observed.amount_captured
  if (result.observed.captures > 0 && amount != null && appCaptures != null) {
    return `The buyer paid ${amount} ${run.scenario.expect.currency} and the shop recorded ${appCaptures} ${appCaptures === 1 ? 'capture' : 'captures'}.`
  }
  return `PayPal recorded ${captureText(run, false)} and the shop recorded ${captureText(run, true)}.`
}

function RecentRunsTable({ runs, loading, offline }: Pick<PageProps, 'runs' | 'loading' | 'offline'>) {
  const recent = sortedRuns(runs).slice(0, 4)
  const emptyText = loading
    ? 'Loading runs…'
    : offline
      ? "Can't load runs while the engine is unreachable."
      : 'No runs have been recorded yet.'

  return (
    <div className="s02-table-wrap">
      <table className="s02-table s02-runs-table">
        <thead>
          <tr>
            <th scope="col">Run</th>
            <th scope="col">Verdict</th>
            <th scope="col">Fault</th>
            <th scope="col">PayPal recorded</th>
            <th scope="col">App recorded</th>
            <th scope="col">Gap</th>
            <th scope="col">When</th>
          </tr>
        </thead>
        <tbody>
          {recent.length === 0 ? (
            <tr><td colSpan={7} className="s02-empty-cell">{emptyText}</td></tr>
          ) : recent.map((run) => (
            <tr key={run.run_id}>
              <td className="mono">
                <a className="s02-run-link" href={`/live/runs/${encodeURIComponent(run.run_id)}`}>
                  {shortId(run.run_id)}
                </a>
              </td>
              <td><VerdictChip run={run} /></td>
              <td>{faultLabel(run.scenario.fault)}</td>
              <td>{captureText(run, false)}</td>
              <td>{captureText(run, true)}</td>
              <td className="s02-numeric">{gapText(run)}</td>
              <td>{timeAgo(run.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="s02-table-foot">
        <span>{runs.length} stored {runs.length === 1 ? 'run' : 'runs'}</span>
        <a href="/live/runs">View all runs</a>
      </div>
    </div>
  )
}

export function OverviewPage(props: PageProps) {
  const { runs } = props
  const latest = sortedRuns(runs)[0]
  const waitingForRuns = props.loading && runs.length === 0
  const coveredFaults = new Set(runs.map((run) => run.scenario.fault)).size
  const failed = runs.filter((run) => run.result?.verdict === 'FAIL').length
  const passed = runs.filter((run) => run.result?.verdict === 'PASS').length
  const errors = runs.filter((run) => run.result?.verdict === 'ERROR').length
  const latestStatus = waitingForRuns
    ? 'Loading stored runs…'
    : props.offline && runs.length === 0
      ? 'The engine is unreachable; run history could not be loaded.'
      : !latest
    ? 'No runs yet.'
    : latest.result
      ? `The latest run is ${latest.result.verdict.toLowerCase()}.`
      : 'The latest run is still in progress.'
  const nextFault = FAULT_CATALOG.find((fault) =>
    fault.fixturePrepared && !runs.some((run) => run.scenario.fault === fault.code),
  )

  return (
    <section className="s02-view s02-overview">
      <h1 id="page-title-overview">Overview</h1>
      <p className="s02-lead">{coveredFaults} of {FAULT_CATALOG.length} faults have stored runs. {latestStatus}</p>

      <div className="s02-figs" aria-label="Run totals">
        <div><b>{waitingForRuns ? '—' : runs.length}</b><span>runs</span></div>
        <div><b className="s02-number-fail">{waitingForRuns ? '—' : failed}</b><span>failed</span></div>
        <div><b className="s02-number-pass">{waitingForRuns ? '—' : passed}</b><span>passed</span></div>
        <div><b>{waitingForRuns ? '—' : errors}</b><span>could not run</span></div>
      </div>

      <div className="s02-section-heading">
        <h2>Latest runs</h2>
      </div>
      <RecentRunsTable {...props} />

      <h2 className="s02-subheading">Next steps</h2>
      <div className="s02-next-step">
        <p>
          {waitingForRuns
            ? 'Loading scenario coverage…'
            : nextFault
            ? `Next prepared scenario without a stored run: ${faultLabel(nextFault.code)}.`
            : 'All prepared scenarios have stored runs. Review their evidence and verdicts.'}
        </p>
        <a href="/live/faults">View fault coverage</a>
      </div>
    </section>
  )
}

export function RunsPage(props: PageProps) {
  const columns = [
    { key: 'run', label: 'Run', value: (run: Run) => run.run_id },
    { key: 'verdict', label: 'Verdict', value: (run: Run) => run.result?.verdict ?? 'RUNNING' },
    { key: 'fault', label: 'Fault', value: (run: Run) => faultLabel(run.scenario.fault) },
    { key: 'paypal', label: 'PayPal recorded', value: (run: Run) => captureText(run, false) },
    { key: 'app', label: 'App recorded', value: (run: Run) => captureText(run, true) },
    { key: 'gap', label: 'Gap', value: gapText },
    { key: 'when', label: 'When', value: (run: Run) => timeAgo(run.created_at) },
  ] as const
  const [filters, setFilters] = useState<Record<string, string>>({})
  const orderedRuns = sortedRuns(props.runs)
  const filteredRuns = orderedRuns.filter((run) => columns.every(({ key, value }) =>
    value(run).toLocaleLowerCase().includes((filters[key] ?? '').trim().toLocaleLowerCase()),
  ))
  const openRun = (runId: string) => {
    window.location.assign(`/live/runs/${encodeURIComponent(runId)}`)
  }

  return (
    <section className="s02-view s02-run-view">
      <h1 id="page-title-runs">Runs</h1>
      <p className="s02-lead">Click a row to open it. Type in a filter box to narrow a column.</p>
      {props.loading && props.runs.length === 0 ? (
        <p className="muted" role="status">Loading runs…</p>
      ) : props.offline && props.runs.length === 0 ? (
        <p className="muted">Can&apos;t load runs while the engine is unreachable.</p>
      ) : (
        <div className="s02-table-wrap">
          <table className="s02-table s02-run-table">
            <thead>
              <tr>{columns.map((column) => <th scope="col" key={column.key}>{column.label}</th>)}</tr>
              <tr className="s02-filter-row">
                {columns.map((column) => (
                  <td key={column.key}>
                    <input
                      type="search"
                      value={filters[column.key] ?? ''}
                      aria-label={`Filter ${column.label.toLowerCase()}`}
                      placeholder="Filter"
                      onChange={(event) => setFilters((current) => ({ ...current, [column.key]: event.target.value }))}
                    />
                  </td>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRuns.length === 0 ? (
                <tr><td colSpan={columns.length} className="s02-empty-cell">{orderedRuns.length === 0 ? 'No runs yet.' : 'No runs match these filters.'}</td></tr>
              ) : filteredRuns.map((run) => (
                <tr
                  key={run.run_id}
                  data-run-link
                  onClick={(event) => {
                    if ((event.target as HTMLElement).closest('a,button')) return
                    openRun(run.run_id)
                  }}
                >
                  <td className="mono">
                    <a className="s02-run-link" href={`/live/runs/${encodeURIComponent(run.run_id)}`}>
                      {shortId(run.run_id)}
                    </a>
                  </td>
                  <td><VerdictChip run={run} /></td>
                  <td>{faultLabel(run.scenario.fault)}</td>
                  <td>{captureText(run, false)}</td>
                  <td>{captureText(run, true)}</td>
                  <td className="s02-numeric">{gapText(run)}</td>
                  <td>{timeAgo(run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="s02-runs-footer">
            <span>{filteredRuns.length} of {props.runs.length} {props.runs.length === 1 ? 'run' : 'runs'}</span>
            <a href="/live/overview">Overview</a>
          </div>
        </div>
      )}
    </section>
  )
}

export function FaultsPage({ runs, loading, offline }: PageProps) {
  const orderedRuns = sortedRuns(runs)

  return (
    <section className="s02-view">
      <h1 id="page-title-faults">Faults</h1>
      <p className="s02-lead">The seven ways DriftGuard breaks a checkout.</p>
      <p className="s02-note">
        {loading && runs.length === 0
          ? 'Loading run history. Fixture availability describes local contract data; it does not imply a live Sandbox run.'
          : offline && runs.length === 0
            ? 'The engine is unreachable. No run history is available; fixture availability does not imply a live Sandbox run.'
            : runs.some((run) => run.mode === 'sample')
              ? 'Run counts and verdicts here come from prepared sample fixtures. They do not imply new PayPal Sandbox execution.'
              : 'Run counts and latest verdicts come from stored engine runs. Fixture availability describes local contract data and does not imply a live Sandbox run.'}
      </p>
      <div className="s02-table-wrap">
        <table className="s02-table s02-fault-table">
          <thead>
            <tr>
              <th scope="col">Fault</th>
              <th scope="col">Name</th>
              <th scope="col">What it does</th>
              <th scope="col">Runs</th>
              <th scope="col">Latest</th>
            </tr>
          </thead>
          <tbody>
            {FAULT_CATALOG.map((fault) => {
              const faultRuns = orderedRuns.filter((run) => run.scenario.fault === fault.code)
              const latest = faultRuns[0]
              return (
                <tr key={fault.code}>
                  <td className="mono"><b>{fault.code.split('_')[0]}</b></td>
                  <td>{fault.name}</td>
                  <td className="s02-fault-description">{fault.description}</td>
                  <td className="s02-numeric">{faultRuns.length}</td>
                  <td>
                    {latest?.result
                      ? <a className="s02-fault-latest" href={`/live/runs/${encodeURIComponent(latest.run_id)}`}><VerdictChip run={latest} /></a>
                      : latest
                        ? <span className="muted">Running</span>
                        : <span className="muted">{loading ? 'Loading' : 'Not run yet'}</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function RunDetailPage({
  run,
  runs,
  loading,
  offline,
  busy,
  fix,
  onBack,
  onRerun,
  onPropose,
}: {
  run: Run | null
  runs: Run[]
  loading: boolean
  offline: boolean
  busy: boolean
  fix: FixState | undefined
  onBack: () => void
  onRerun: (runId: string) => void
  onPropose: () => void
}) {
  const [tab, setTab] = useState<'overview' | 'evidence' | 'fix'>('overview')
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  if (!run) {
    return (
      <section className="s02-view">
        <h1 id="page-title-run">{loading ? 'Loading run…' : 'Run not found'}</h1>
        <p className="s02-lead">{offline ? "Can't load this run while the engine is unreachable." : 'This run is not in the engine’s stored results.'}</p>
        {!loading && <button className="s02-text-button" type="button" onClick={onBack}>Back to runs</button>}
      </section>
    )
  }

  const { result, scenario } = run
    const cliCommand = `python -m cli run ${scenario.fault.split('_')[0]}`
  const rerun = runs.find((candidate) => candidate.rerun_of === run.run_id)
  const parent = run.rerun_of ? runs.find((candidate) => candidate.run_id === run.rerun_of) : undefined
  const comparisonBefore = parent ? parent : run
  const comparisonAfter = parent ? run : rerun
  const failed = result?.verdict === 'FAIL'
  const copyCommand = async () => {
    try {
      await navigator.clipboard.writeText(cliCommand)
      setCopyState('copied')
    } catch {
      setCopyState('failed')
    }
  }

  return (
    <section className="s02-view s02-detail-view">
      <div className="s02-detail-head">
        <div>
          <div className="s02-breadcrumb"><a href="/live/runs">Runs</a><span aria-hidden="true">/</span><span>{shortId(run.run_id)}</span></div>
          <h1 id="page-title-run">{runSummary(run)}</h1>
          <p className="s02-lead"><VerdictChip run={run} /> <span>{faultLabel(scenario.fault)}, {timeAgo(run.created_at)}</span></p>
        </div>
        <div className="s02-detail-actions">
          <button className="btn" type="button" onClick={() => void copyCommand()}>
            {copyState === 'copied' ? 'Copied' : 'Copy CLI command'}
          </button>
          <button className="btn btn-primary" type="button" disabled={busy} onClick={() => onRerun(run.run_id)}>
              {busy ? 'Starting…' : run.mode === 'sample' ? 'Show sample outcome' : failed ? 'Generate and verify fix' : 'Re-run scenario'}
          </button>
        </div>
      </div>

      {copyState === 'failed' && <p className="muted small" role="status">Copy failed. The command is shown in Evidence.</p>}
      <div className="s02-detail-tabs" role="tablist" aria-label="Run details">
        {(['overview', 'evidence', 'fix'] as const).map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            className={tab === name ? 'is-active' : ''}
            onClick={() => setTab(name)}
          >
            {name === 'overview' ? 'Overview' : name === 'evidence' ? 'Evidence' : 'Fix'}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="s02-detail-panel">
          {!result ? (
            <div className="notice" role="status"><strong>Waiting for the reconciler</strong><p>PayPal&apos;s records have not been returned yet.</p></div>
          ) : result.verdict === 'ERROR' ? (
            <div className="notice notice-error"><strong>The test could not complete</strong><p>{result.error_message || result.rule}</p></div>
          ) : (
            <>
              <ComparisonProof before={comparisonBefore} after={comparisonAfter} focusAfter={Boolean(parent)} />
              <h2>What happened</h2>
              <ul className="s02-timeline">
                <li><i aria-hidden="true" /><span>{run.mode === 'sample' ? 'The sample illustrates' : 'DriftGuard injected'} {scenario.inject.action} on {scenario.inject.on}.</span></li>
                <li><i aria-hidden="true" /><span>{run.mode === 'sample' ? 'The sample PayPal state shows' : 'PayPal recorded'} {captureText(run, false)}{result.observed.amount_captured == null ? '' : ` for ${result.observed.amount_captured} ${scenario.expect.currency}`}.</span></li>
                <li className={result.observed.app_recorded_captures === result.observed.captures ? 'is-good' : 'is-bad'}><i aria-hidden="true" /><span>{run.mode === 'sample' ? 'The sample app state shows' : 'The shop recorded'} {captureText(run, true)}.</span></li>
                <li className={result.verdict === 'PASS' ? 'is-good' : 'is-bad'}><i aria-hidden="true" /><span>The <code>{result.rule}</code> check returned {result.verdict}.</span></li>
              </ul>
            </>
          )}
        </div>
      )}

      {tab === 'evidence' && (
        <div className="s02-detail-panel">
          {!result ? <p className="muted">Evidence is not available until this run completes.</p> : (
            <>
              <h2>{run.mode === 'sample' ? 'Sample evidence fields' : 'Evidence from PayPal Sandbox'}</h2>
              {run.mode === 'sample' && <p className="muted small">These fixture IDs are examples, not a new PayPal transaction from this page.</p>}
              <EvidenceList title="Order IDs" values={result.evidence.paypal_order_ids} />
              <EvidenceList title="Capture IDs" values={result.evidence.paypal_capture_ids} />
              <EvidenceList title="Refund IDs" values={result.evidence.paypal_refund_ids} />
              <EvidenceList title="Proxy log references" values={result.evidence.proxy_log_refs} />
              <EvidenceList title="Webhook event IDs" values={result.evidence.webhook_event_ids} />
              <h2>Expected vs observed</h2>
              <ExpectedObservedTable run={run} />
              <h2>CLI command</h2>
              <pre className="s02-command">{cliCommand}</pre>
              {copyState === 'failed' && <p className="muted small">Clipboard access is unavailable here; copy the command above.</p>}
              <h2>Scenario</h2>
              <dl className="s02-scenario-details">
                <dt>Call site</dt><dd className="mono">{scenario.target_call.file}:{scenario.target_call.line}</dd>
                <dt>Method</dt><dd className="mono">{scenario.target_call.method ?? '—'}</dd>
                <dt>Injected</dt><dd className="mono">{scenario.inject.action} on {scenario.inject.on}</dd>
              </dl>
            </>
          )}
        </div>
      )}

      {tab === 'fix' && (
        <div className="s02-detail-panel">
          {run.fix?.proposal ? (
            <>
              <p className="s02-lead">{run.mode === 'sample' ? 'This is a prepared PASS fixture. The hosted preview did not apply the patch or make a new PayPal purchase.' : <>This exact patch ran in a disposable shop copy. The reconciler returned <strong>{result?.verdict ?? 'no verdict yet'}</strong>.</>}</p>
              <p className="muted small mono">{run.mode === 'sample' ? 'Curated patch' : 'Patch'} SHA-256: {run.fix.patch_sha256}</p>
              <FixPanel state={{ status: 'ready', proposal: run.fix.proposal }} onRetry={onPropose} sample={run.mode === 'sample'} />
            </>
          ) : !failed ? <p className="muted">A fix proposal is available for failed runs.</p> : (
            <>
              <p className="s02-lead">The Fixer proposes a patch. DriftGuard checks it before showing it.</p>
              {fix ? <FixPanel state={fix} onRetry={onPropose} sample={run.mode === 'sample'} /> : <button className="btn btn-primary" type="button" onClick={onPropose}>{run.mode === 'sample' ? 'View sample patch' : 'Propose fix'}</button>}
            </>
          )}
        </div>
      )}
    </section>
  )
}

function isRevealedPass(run?: Run): boolean {
  return run?.result?.verdict === 'PASS' && (run.mode === 'sample' || Boolean(run.fix?.patch_sha256))
}

function ComparisonProof({ before, after, focusAfter = false }: { before: Run; after?: Run; focusAfter?: boolean }) {
  const [pop, setPop] = useState(false)
  const proofRef = useRef<HTMLDivElement>(null)
  const splitRef = useRef(80)
  const autoRef = useRef(true)
  const resultText = (run: Run) => {
    if (!run.result) return 'PayPal is still checking this run.'
    if (run.result.verdict === 'ERROR') return 'The test could not finish.'
    const appCount = run.result.observed.app_recorded_captures
    return `${run.mode === 'sample' ? 'Sample: PayPal' : 'PayPal'} ${run.result.observed.captures} capture${run.result.observed.captures === 1 ? '' : 's'}. ${run.mode === 'sample' ? 'App state' : 'Your app'} ${appCount == null ? 'has no reading' : `${appCount} capture${appCount === 1 ? '' : 's'}`}.`
  }
  const toneClass = (run?: Run) => {
    const verdict = run?.result?.verdict
    if (!verdict) return 'is-pending'
    if (verdict === 'PASS') return isRevealedPass(run) ? 'is-good' : 'is-pending'
    return 'is-bad'
  }
  const hasAfter = Boolean(after)
  const afterRevealedPass = isRevealedPass(after)
  const afterLiveVerified = after?.mode !== 'sample' && after?.result?.verdict === 'PASS' && Boolean(after.fix?.patch_sha256)

  useEffect(() => {
    const proof = proofRef.current
    if (!proof) return
    // Only slide open to PASS when viewing the repeat/PASS run itself; keep a FAIL run focused on FAIL.
    const endAt = focusAfter && afterRevealedPass ? 20 : 80
    if ((!focusAfter && hasAfter) || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      splitRef.current = endAt
      proof.style.setProperty('--split', `${endAt}%`)
      return
    }

    let cancelled = false
    let started = false
    let frame = 0
    let kickoff: number | undefined
    let popTimer: number | undefined
    let seen = false
    const setPosition = (value: number) => {
      splitRef.current = value
      proof.style.setProperty('--split', `${value}%`)
      if (value < 40 && !seen && afterLiveVerified) {
        seen = true
        setPop(true)
        if (popTimer != null) window.clearTimeout(popTimer)
        popTimer = window.setTimeout(() => setPop(false), 1300)
      } else if (value > 60) {
        seen = false
      }
    }
    const animate = (from: number, to: number, done: () => void) => {
      const startedAt = performance.now()
      const tick = (now: number) => {
        if (cancelled || !autoRef.current) return
        const progress = Math.min(1, (now - startedAt) / 1900)
        const eased = progress < 0.5
          ? 2 * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 2) / 2
        setPosition(from + (to - from) * eased)
        if (progress < 1) frame = window.requestAnimationFrame(tick)
        else done()
      }
      frame = window.requestAnimationFrame(tick)
    }
    const demo = () => {
      if (cancelled || !autoRef.current) return
      const stops = [splitRef.current, 92, 8, endAt]
      let leg = 0
      const next = () => {
        if (cancelled || !autoRef.current || leg >= stops.length - 1) return
        const from = stops[leg]
        const to = stops[leg + 1]
        leg += 1
        animate(from, to, next)
      }
      next()
    }
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && !started) {
          started = true
          kickoff = window.setTimeout(demo, 500)
        }
      }
    }, { threshold: 0.6 })
    observer.observe(proof)

    return () => {
      cancelled = true
      observer.disconnect()
      if (kickoff != null) window.clearTimeout(kickoff)
      if (popTimer != null) window.clearTimeout(popTimer)
      window.cancelAnimationFrame(frame)
    }
  }, [afterRevealedPass, afterLiveVerified, focusAfter, hasAfter])

  const handleSplit = (value: number) => {
    autoRef.current = false
    splitRef.current = value
    proofRef.current?.style.setProperty('--split', `${value}%`)
    if (value < 40 && afterLiveVerified) setPop(true)
    else setPop(false)
  }

  return (
    <section className="s02-comparison">
      <h2>Before and after</h2>
      <div ref={proofRef} className={`s02-proof${pop ? ' is-pop' : ''}`}>
        <div className={`s02-proof-side s02-proof-before ${toneClass(before)}`}>
          <span>{before.mode === 'sample' ? 'Sample original' : 'Original run'}</span>
          <strong>{before.result?.verdict ?? 'RUNNING'}</strong>
          <p>{resultText(before)}</p>
        </div>
        <div className={`s02-proof-side s02-proof-after ${toneClass(after)}`}>
          <span>{(after?.mode ?? before.mode) === 'sample' ? 'Sample repeat' : 'Repeat run'}</span>
          <strong>{after?.result?.verdict ?? (after ? 'RUNNING' : 'NOT RUN')}</strong>
          <p>{after ? resultText(after) : before.mode === 'sample' ? 'Show the prepared PASS fixture to compare sample results.' : 'Generate and verify a fix to compare results.'}</p>
        </div>
        <div className="s02-proof-divider" aria-hidden="true" />
        <span className="s02-proof-knob" aria-hidden="true">↔</span>
        <input
          className="s02-proof-slider"
          type="range"
          min="0"
          max="100"
          defaultValue="80"
          aria-label="Reveal the before and after results"
          onChange={(event) => handleSplit(Number(event.target.value))}
        />
      </div>
      <p className="s02-proof-caption">
        {!focusAfter && after ? (
          <>
            {after.mode === 'sample'
              ? 'This sample failed. Prepared PASS fixture '
              : after.fix?.patch_sha256
                ? 'This run failed. A later patched repeat ('
                : 'This run failed. A later repeat ('}
            <a className="s02-run-link" href={`/live/runs/${encodeURIComponent(after.run_id)}`}>{shortId(after.run_id)}</a>
            {after.mode === 'sample'
              ? ' is available for comparison — drag left to preview.'
              : after.fix?.patch_sha256
                ? ') passed — drag left to compare.'
                : ') exists — drag left to compare.'}
          </>
        ) : after?.mode === 'sample'
          ? 'Prepared PASS fixture shown for comparison. No patch was applied and no new PayPal order was made.'
          : after?.fix?.patch_sha256
            ? 'Same scenario, new PayPal order, patched shop copy. The patch and verdict are stored with this run.'
            : after
              ? 'This repeat has no verified patch, so it cannot prove a fix.'
              : before.mode === 'sample'
                ? 'Show the sample outcome to compare both fixtures.'
                : 'Generate and verify a fix to compare both runs.'}
      </p>
    </section>
  )
}

function ExpectedObservedTable({ run }: { run: Run }) {
  if (!run.result) return <p className="muted">Expected and observed values are available after the run completes.</p>
  const { result, scenario } = run

  return (
    <table className="compare">
      <thead><tr><th /><th>Expected</th><th>Observed</th></tr></thead>
      <tbody>
        <tr>
          <td>PayPal captures</td>
          <td className="mono">{scenario.expect.captures_per_purchase}</td>
          <td className={`mono ${result.observed.captures !== scenario.expect.captures_per_purchase ? 'bad' : ''}`}>{result.observed.captures}</td>
        </tr>
        <tr>
          <td>App recorded captures</td>
          <td className="mono">{result.observed.captures}</td>
          <td className={`mono ${result.observed.app_recorded_captures !== result.observed.captures ? 'bad' : ''}`}>{result.observed.app_recorded_captures ?? 'No reading'}</td>
        </tr>
        <tr>
          <td>Amount ({scenario.expect.currency})</td>
          <td className="mono">{scenario.expect.amount ?? '—'}</td>
          <td className="mono">{result.observed.amount_captured ?? 'No reading'}</td>
        </tr>
      </tbody>
    </table>
  )
}

function EvidenceList({ title, values }: { title: string; values: string[] }) {
  return (
    <section className="s02-evidence-list">
      <h3>{title}</h3>
      {values.length === 0
        ? <p className="muted">No {title.toLowerCase()} recorded.</p>
        : <ul>{values.map((value) => <li key={value}><code>{value}</code></li>)}</ul>}
    </section>
  )
}

export function DocsPage() {
  return (
    <section className="s02-view s02-docs-view">
      <h1 id="page-title-docs">Connect a shop</h1>
      <p className="s02-lead">Three steps. Nothing is installed in the shop.</p>

      <section className="s02-doc-step">
        <h2>1. Point the test at your Sandbox</h2>
        <p>Use a PayPal Sandbox app and your shop&apos;s test URL. Keep client credentials in the engine&apos;s <code>.env</code> file; never paste them into the dashboard.</p>
      </section>
      <section className="s02-doc-step">
        <h2>2. Start the local services</h2>
        <p>Start the proxy and database, then the engine API and demo shop.</p>
        <pre className="s02-command">docker compose up -d{`\n`}python -m uvicorn engine.api.main:app --port 8000 --reload{`\n`}npm --prefix targets/demo-shop run dev</pre>
      </section>
      <section className="s02-doc-step">
        <h2>3. Run a fault and read the report</h2>
        <p>Use the run button to start F1. Open a row in Runs to compare PayPal&apos;s records with the shop&apos;s evidence.</p>
        <a className="btn btn-primary s02-doc-link" href="/live/runs">Open runs</a>
      </section>

      <section className="s02-doc-step s02-ci-note">
        <h2>Use it in CI</h2>
        <p>Treat a <b className="s02-number-fail">FAIL</b> or <b className="s02-number-fail">ERROR</b> verdict as a failed check. Verdicts come from the engine&apos;s recorded evidence, not an AI answer.</p>
      </section>
    </section>
  )
}
