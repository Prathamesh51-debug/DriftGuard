import type { FixProposal, FixState } from '../types'
import { classifyDiffLine } from '../beforeAfter'

export function DiffView({ diff }: { diff: string }) {
  const lines = diff.replace(/\n$/, '').split('\n')
  return (
    <pre className="diff" aria-label="Proposed code change">
      {lines.map((line, i) => (
        <span key={i} className={`diff-line diff-${classifyDiffLine(line)}`}>
          {line || ' '}
        </span>
      ))}
    </pre>
  )
}

function origin(p: FixProposal): string {
  return p.source === 'llm' ? `Written by ${p.provider ?? 'the model'}, checked by code` : 'Curated fix selected by code'
}

export function FixPanel({ state, onRetry }: { state: FixState; onRetry: () => void }) {
  if (state.status === 'loading') {
    return (
      <div className="notice" role="status">
        <strong>Asking the Fixer…</strong>
        <p className="muted small">A live model can take up to a minute. Nothing is changed in the shop.</p>
      </div>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="notice notice-error" role="alert">
        <strong>No fix this time</strong>
        <p>{state.message}</p>
        <button className="link-btn" onClick={onRetry}>
          Try again
        </button>
      </div>
    )
  }
  const p = state.proposal
  if (!p.applies || !p.diff) {
    return (
      <div className="notice notice-error" role="alert">
        <strong>The Fixer found no safe change</strong>
        <p>{p.error ?? 'Every attempt was rejected by the checks.'}</p>
        <button className="link-btn" onClick={onRetry}>
          Try again
        </button>
      </div>
    )
  }
  return (
    <div className="fix">
      <div className="fix-meta">
        <span className="chip chip-pass">
          <span aria-hidden="true">✓</span>Checks passed
        </span>
        <span className="muted small">{origin(p)}</span>
      </div>
      {p.source === 'llm' && p.explanation && <p>{p.explanation}</p>}
      <p className="muted small mono">
        {p.files.join(', ')} · {p.lines_changed} lines changed
      </p>
      <DiffView diff={p.diff} />
      <p className="muted small">Applies cleanly to a copy of the shop. It is not applied to the shop itself.</p>
    </div>
  )
}
