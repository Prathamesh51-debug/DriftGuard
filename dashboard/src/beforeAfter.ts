import type { Run } from './types'

/** What the before/after view concludes. Only "fixed" is green: the same chaos run must now PASS. */
export type CompareOutcome = 'waiting' | 'fixed' | 'still_failing' | 'error' | 'not_comparable'

export function compareOutcome(before: Run, after: Run | undefined): CompareOutcome {
  if (before.result?.verdict !== 'FAIL') return 'not_comparable'
  if (!after?.result) return 'waiting'
  switch (after.result.verdict) {
    case 'PASS':
      return 'fixed'
    case 'FAIL':
      return 'still_failing'
    default:
      return 'error'
  }
}

/** The run that repeats this one (newest first, as the engine lists them), if any. */
export const rerunOf = (runs: Run[], runId: string): Run | undefined => runs.find((r) => r.rerun_of === runId)

/** The run a re-run repeats, if it is still in the list. */
export const originalOf = (runs: Run[], run: Run): Run | undefined =>
  run.rerun_of ? runs.find((r) => r.run_id === run.rerun_of) : undefined

export type DiffLineKind = 'add' | 'del' | 'hunk' | 'meta' | 'ctx'

export function classifyDiffLine(line: string): DiffLineKind {
  if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff ') || line.startsWith('index ')) return 'meta'
  if (line.startsWith('@@')) return 'hunk'
  if (line.startsWith('+')) return 'add'
  if (line.startsWith('-')) return 'del'
  return 'ctx'
}

/** A plain-words account of an ERROR result, with the engine's own text kept as detail. */
export function describeError(rule: string, message: string | null): { headline: string; detail: string | null } {
  if (rule === 'target_reachable') {
    return { headline: "The demo shop didn't answer, so the test could not run. Start the shop and run it again.", detail: message }
  }
  return { headline: 'The engine could not finish this run.', detail: message }
}
