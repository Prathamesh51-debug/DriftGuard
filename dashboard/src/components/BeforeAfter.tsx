import { useEffect } from 'react'
import type { FixProposal, Run } from '../types'
import { compareOutcome, describeError, type CompareOutcome } from '../beforeAfter'
import { elapsedSeconds, faultLabel, shortId } from '../format'
import { VerdictChip } from './VerdictChip'
import { DiffView } from './FixPanel'

function Side({ title, run, tone }: { title: string; run: Run | undefined; tone: 'before' | 'after' }) {
  const result = run?.result
  const expected = run?.scenario.expect
  const mismatch = result && expected && result.observed.captures !== expected.captures_per_purchase
  const appLost = result?.observed.app_recorded_captures != null && result.observed.app_recorded_captures !== result.observed.captures
  return (
    <section className={`ba-side ba-${tone}`} aria-label={title}>
      <header>
        <div className="eyebrow">{title}</div>
        {run && <VerdictChip run={run} />}
      </header>
      {!run || !result ? (
        <div className="notice" role="status">
          <strong>Re-running the same scenario…</strong>
          <p className="muted small">{run ? `${elapsedSeconds(run.created_at)}s so far.` : 'Starting.'}</p>
        </div>
      ) : result.verdict === 'ERROR' ? (
        <>
          <p className="muted small mono">Run {shortId(run.run_id)}</p>
          <p className="impact">{describeError(result.rule, result.error_message).headline}</p>
          <p className="muted small">No numbers are shown because PayPal was never checked for this run.</p>
        </>
      ) : (
        <>
          <p className="muted small mono">Run {shortId(run.run_id)}</p>
          <dl className="ba-numbers">
            <div>
              <dt>Captures in PayPal</dt>
              <dd className={`mono ${mismatch ? 'bad' : ''}`}>{result.observed.captures}</dd>
            </div>
            {result.observed.app_recorded_captures != null && (
              <div>
                <dt>Captures the app recorded</dt>
                <dd className={`mono ${appLost ? 'bad' : 'good'}`}>{result.observed.app_recorded_captures}</dd>
              </div>
            )}
            <div>
              <dt>Amount captured</dt>
              <dd className="mono">
                {result.observed.amount_captured} {expected?.currency}
              </dd>
            </div>
          </dl>
          <p className="impact">{result.money_impact}</p>
        </>
      )}
    </section>
  )
}

const VERDICT_TEXT: Record<CompareOutcome, { cls: string; title: string; body: string }> = {
  waiting: { cls: '', title: 'Re-running…', body: 'The same chaos scenario is running again, and PayPal is being checked.' },
  fixed: { cls: 'notice-pass', title: 'Fixed, and PayPal agrees', body: 'The same scenario that lost a payment now passes: PayPal and the app record the same capture.' },
  still_failing: { cls: 'notice-error', title: 'Still failing', body: 'The same scenario fails again, so this change did not fix the problem.' },
  error: { cls: 'notice-error', title: 'The re-run could not finish', body: 'No verdict was reached, so nothing is proven either way.' },
  not_comparable: { cls: '', title: 'Fix not proven', body: 'A passing repeat alone does not prove the proposed code was applied. A verified patch and a passing run are both required.' },
}

export function BeforeAfter({
  before,
  after,
  proposal,
  onClose,
}: {
  before: Run
  after: Run | undefined
  proposal: FixProposal | undefined
  onClose: () => void
}) {
  useEffect(() => {
    // Capture phase and stop: the overlay sits above the drawer, so Escape closes only the overlay.
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.stopImmediatePropagation()
      onClose()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [onClose])

  const outcome = compareOutcome(before, after)
  const verdict = VERDICT_TEXT[outcome]
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Before and after the fix">
      <div className="ba">
        <header className="ba-head">
          <div>
            <div className="eyebrow">{faultLabel(before.scenario.fault)}</div>
            <h2>Before and after</h2>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close before and after view">
            ✕
          </button>
        </header>
        <div className={`notice ba-verdict ${verdict.cls}`} role="status">
          <strong>{verdict.title}</strong>
          <p>{verdict.body}</p>
        </div>
        <div className="ba-sides">
          <Side title="Before the fix" run={before} tone="before" />
          <Side title="After the fix" run={after} tone="after" />
        </div>
        {proposal?.diff && (
          <section className="ba-diff">
            <h3>The fix</h3>
            {proposal.explanation && <p className="muted">{proposal.explanation}</p>}
            <DiffView diff={proposal.diff} />
          </section>
        )}
      </div>
    </div>
  )
}
