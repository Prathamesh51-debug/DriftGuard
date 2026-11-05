import { useEffect, useRef, useState } from 'react'
import type { FixState, Result, Run } from '../types'
import { elapsedSeconds, faultLabel, shortId } from '../format'
import { VerdictChip } from './VerdictChip'
import { FixPanel } from './FixPanel'
import { describeError } from '../beforeAfter'

const SLOW_RUN_SECONDS = 60

function Waiting({ seconds }: { seconds: number }) {
  return (
    <div className="notice" role="status">
      <strong>Waiting for the reconciler</strong>
      <p>Reading PayPal&apos;s records for this run. {seconds}s so far.</p>
      {seconds > SLOW_RUN_SECONDS && (
        <p className="muted small">This is taking longer than usual. The engine may be stuck.</p>
      )}
    </div>
  )
}

function Outcome({ result }: { result: Result }) {
  if (result.verdict === 'ERROR') {
    const err = describeError(result.rule, result.error_message)
    return (
      <div className="notice notice-error" role="alert">
        <strong>The test could not complete</strong>
        <p>{err.headline}</p>
        {err.detail && (
          <details className="err-detail">
            <summary>Technical details</summary>
            <p className="mono small">{err.detail}</p>
          </details>
        )}
        <p className="muted small">No verdict was reached, so there is nothing to fix yet.</p>
      </div>
    )
  }
  if (result.verdict === 'PASS') {
    return (
      <div className="notice notice-pass">
        <strong>No problem found</strong>
        <p>{result.money_impact}</p>
      </div>
    )
  }
  return <p className="impact">{result.money_impact}</p>
}

function IdList({ title, ids }: { title: string; ids: string[] }) {
  const [copied, setCopied] = useState<string | null>(null)
  if (ids.length === 0) return null

  const copy = (id: string) => {
    navigator.clipboard?.writeText(id).then(() => {
      setCopied(id)
      setTimeout(() => setCopied(null), 1200)
    })
  }

  return (
    <div className="idlist">
      <h4>{title}</h4>
      {ids.map((id) => (
        <button key={id} className="idrow mono" onClick={() => copy(id)} title="Copy">
          <span>{id}</span>
          <span className="muted">{copied === id ? 'copied' : 'copy'}</span>
        </button>
      ))}
    </div>
  )
}

export function EvidenceDrawer({
  run,
  busy,
  fix,
  compare,
  onClose,
  onRerun,
  onPropose,
}: {
  run: Run
  busy: boolean
  fix: FixState | undefined
  compare: { label: string; open: () => void } | null
  onClose: () => void
  onRerun: (runId: string) => void
  onPropose: () => void
}) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    headingRef.current?.focus()
  }, [run.run_id])

  const { scenario, result } = run
  const wantAmount = scenario.expect.amount
  const failed = result?.verdict === 'FAIL'

  return (
    <aside className="drawer" aria-label={`Evidence for run ${shortId(run.run_id)}`}>
      <header className="drawer-head">
        <div>
          <div className="eyebrow">Run {shortId(run.run_id)}</div>
          <h2 ref={headingRef} tabIndex={-1}>{faultLabel(scenario.fault)}</h2>
        </div>
        <div className="drawer-head-actions">
          <a className="drawer-open-page" href={`/live/runs/${encodeURIComponent(run.run_id)}`}>Open full page</a>
          <button className="icon-btn" onClick={onClose} aria-label="Close evidence drawer">
            ✕
          </button>
        </div>
      </header>

      <div className="drawer-body">
        <VerdictChip run={run} />

        {!result ? (
          <Waiting seconds={elapsedSeconds(run.created_at)} />
        ) : (
          <>
            <Outcome result={result} />

            {result.verdict !== 'ERROR' && (
              <>
                <h3 id="proof-chain-heading">Evidence trail</h3>
                <ol className="proof-chain" aria-labelledby="proof-chain-heading">
                  <li>
                    <strong>Configured fault</strong>
                    <span><code>{scenario.inject.action}</code> on <code>{scenario.inject.on}</code></span>
                  </li>
                  <li>
                    <strong>PayPal record</strong>
                    <span>{result.observed.captures} capture(s); {result.observed.amount_captured} {scenario.expect.currency}</span>
                  </li>
                  {result.observed.app_recorded_captures != null && (
                    <li>
                      <strong>App record</strong>
                      <span>{result.observed.app_recorded_captures} capture(s)</span>
                    </li>
                  )}
                  <li>
                    <strong>Rule decision</strong>
                    <span><code>{result.rule}</code> · {result.verdict}</span>
                  </li>
                </ol>
                <p className="muted small proof-note">This trail uses saved run fields; it does not invent event timings.</p>
                <h3>Expected vs observed</h3>
                <table className="compare">
                  <thead>
                    <tr>
                      <th />
                      <th>Expected</th>
                      <th>Observed (PayPal)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Captures (PayPal)</td>
                      <td className="mono">{scenario.expect.captures_per_purchase}</td>
                      <td
                        className={`mono ${result.observed.captures !== scenario.expect.captures_per_purchase ? 'bad' : ''}`}
                      >
                        {result.observed.captures}
                      </td>
                    </tr>
                    {result.observed.app_recorded_captures != null && (
                      <tr>
                        <td>Captures (app&apos;s own records)</td>
                        <td className="mono">{result.observed.captures}</td>
                        <td
                          className={`mono ${result.observed.app_recorded_captures !== result.observed.captures ? 'bad' : ''}`}
                        >
                          {result.observed.app_recorded_captures}
                        </td>
                      </tr>
                    )}
                    <tr>
                      <td>Amount ({scenario.expect.currency})</td>
                      <td className="mono">{wantAmount ?? '—'}</td>
                      <td className={`mono ${wantAmount && wantAmount !== result.observed.amount_captured ? 'bad' : ''}`}>
                        {result.observed.amount_captured}
                      </td>
                    </tr>
                  </tbody>
                </table>
                <p className="muted small mono">rule: {result.rule}</p>
              </>
            )}

            {fix && (
              <>
                <h3>Proposed fix</h3>
                <FixPanel state={fix} onRetry={onPropose} />
              </>
            )}

            <h3>Evidence from PayPal sandbox</h3>
            <IdList title="Order IDs" ids={result.evidence.paypal_order_ids} />
            <IdList title="Capture IDs" ids={result.evidence.paypal_capture_ids} />
            <IdList title="Refund IDs" ids={result.evidence.paypal_refund_ids} />
            <IdList title="Proxy log refs" ids={result.evidence.proxy_log_refs} />
            <IdList title="Webhook event IDs" ids={result.evidence.webhook_event_ids} />
          </>
        )}

        <h3>Scenario</h3>
        <dl className="kv">
          <dt>Call site</dt>
          <dd className="mono">
            {scenario.target_call.file}:{scenario.target_call.line}
          </dd>
          <dt>Method</dt>
          <dd className="mono">{scenario.target_call.method ?? '—'}</dd>
          <dt>Injected</dt>
          <dd className="mono">
            {scenario.inject.action} on {scenario.inject.on}
          </dd>
        </dl>
        {scenario.description && <p className="muted small">{scenario.description}</p>}
      </div>

      {(failed || compare) && (
        <footer className="drawer-foot">
          {compare && (
            <button className="btn btn-primary" onClick={compare.open}>
              {compare.label}
            </button>
          )}
          {failed && (
            <>
              {fix?.status !== 'ready' && (
                <button className="btn" disabled={fix?.status === 'loading'} onClick={onPropose}>
                  {fix?.status === 'loading' ? 'Asking the Fixer…' : 'Propose fix'}
                </button>
              )}
              <button className={`btn ${compare ? '' : 'btn-primary'}`} disabled={busy} onClick={() => onRerun(run.run_id)}>
                {busy ? 'Re-running…' : 'Re-run after fix'}
              </button>
            </>
          )}
        </footer>
      )}
    </aside>
  )
}
