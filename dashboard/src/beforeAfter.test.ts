import { describe, expect, it } from 'vitest'
import scenario from '../../contracts/fixtures/f1_scenario.json'
import fail from '../../contracts/fixtures/f1_result_fail.json'
import pass from '../../contracts/fixtures/f1_result_pass.json'
import type { Run } from './types'
import { classifyDiffLine, compareOutcome, originalOf, rerunOf } from './beforeAfter'

const run = (id: string, result: unknown, rerun_of: string | null = null): Run =>
  ({ run_id: id, status: result ? 'complete' : 'running', created_at: 1, scenario, result, rerun_of }) as unknown as Run

describe('compareOutcome', () => {
  const red = run('run_a', fail)

  it('is fixed only when the repeat of a failing run passes', () => {
    expect(compareOutcome(red, run('run_b', pass, 'run_a'))).toBe('fixed')
  })
  it('says still failing when the repeat fails again', () => {
    expect(compareOutcome(red, run('run_b', fail, 'run_a'))).toBe('still_failing')
  })
  it('waits while the repeat has no result, and while it does not exist yet', () => {
    expect(compareOutcome(red, run('run_b', null, 'run_a'))).toBe('waiting')
    expect(compareOutcome(red, undefined)).toBe('waiting')
  })
  it('reports an error result as an error, never as green', () => {
    const err = { ...fail, verdict: 'ERROR', error_message: 'shop down' }
    expect(compareOutcome(red, run('run_b', err, 'run_a'))).toBe('error')
  })
  it('does not compare a run that did not fail in the first place', () => {
    expect(compareOutcome(run('run_a', pass), run('run_b', pass, 'run_a'))).toBe('not_comparable')
  })
})

describe('finding the pair', () => {
  const a = run('run_a', fail)
  const b = run('run_b', pass, 'run_a')
  it('finds the re-run of a run and the original of a re-run', () => {
    expect(rerunOf([b, a], 'run_a')).toBe(b)
    expect(originalOf([b, a], b)).toBe(a)
  })
  it('returns nothing when there is no pair', () => {
    expect(rerunOf([a], 'run_a')).toBeUndefined()
    expect(originalOf([b], b)).toBeUndefined()
    expect(originalOf([a], a)).toBeUndefined()
  })
})

describe('classifyDiffLine', () => {
  it('tells additions, deletions, hunks, file headers and context apart', () => {
    expect(classifyDiffLine('+  paypalRequestId,')).toBe('add')
    expect(classifyDiffLine('-  old')).toBe('del')
    expect(classifyDiffLine('@@ -1,3 +1,4 @@')).toBe('hunk')
    expect(classifyDiffLine('+++ b/src/checkout.ts')).toBe('meta')
    expect(classifyDiffLine('--- a/src/checkout.ts')).toBe('meta')
    expect(classifyDiffLine('diff --git a/x b/x')).toBe('meta')
    expect(classifyDiffLine(' unchanged')).toBe('ctx')
  })
})
