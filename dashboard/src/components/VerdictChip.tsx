import type { Run } from '../types'

// Status is never colour-only: every chip carries a glyph and a text label.
const LOOK = {
  FAIL: { glyph: '✕', label: 'FAIL', cls: 'fail' },
  PASS: { glyph: '✓', label: 'PASS', cls: 'pass' },
  ERROR: { glyph: '!', label: 'ERROR', cls: 'error' },
  RUNNING: { glyph: '…', label: 'RUNNING', cls: 'running' },
} as const

export function VerdictChip({ run }: { run: Run }) {
  const look = run.result ? LOOK[run.result.verdict] : LOOK.RUNNING
  return (
    <span className={`chip chip-${look.cls}`}>
      <span aria-hidden="true">{look.glyph}</span>
      {look.label}
    </span>
  )
}
