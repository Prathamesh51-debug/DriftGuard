import { useEffect, useState } from 'react'
import type { Run } from '../types'
import { faultLabel, shortId } from '../format'
import { VerdictChip } from './VerdictChip'

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
  onClose,
  onRerun,
}: {
  run: Run
  busy: boolean
  onClose: () => void
  onRerun: (runId: string) => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const { scenario, result } = run
  const wantAmount = scenario.expect.amount
  const failed = result?.verdict === 'FAIL'

  return (
    <aside className="drawer" aria-label={`Evidence for run ${shortId(run.run_id)}`}>
      <header className="drawer-head">
        <div>
          <div className="eyebrow">Run {shortId(run.run_id)}</div>
          <h2>{faultLabel(scenario.fault)}</h2>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close evidence drawer">
          ✕
        </button>
      </header>

      <div className="drawer-body">
        <VerdictChip run={run} />

        {!result ? (
          <p className="muted">Waiting for the reconciler to read PayPal&apos;s records…</p>
        ) : (
          <>
            <p className="impact">{result.money_impact}</p>
            {result.error_message && <p className="bad">{result.error_message}</p>}

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
                  <td>Captures</td>
                  <td className="mono">{scenario.expect.captures_per_purchase}</td>
                  <td
                    className={`mono ${result.observed.captures !== scenario.expect.captures_per_purchase ? 'bad' : ''}`}
                  >
                    {result.observed.captures}
                  </td>
                </tr>
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

      {failed && (
        <footer className="drawer-foot">
          <button className="btn btn-primary" disabled={busy} onClick={() => onRerun(run.run_id)}>
            {busy ? 'Re-running…' : 'Re-run after fix'}
          </button>
        </footer>
      )}
    </aside>
  )
}
