import { describe, expect, it } from 'vitest'
import scenario from '../../contracts/fixtures/f1_scenario.json'
import fail from '../../contracts/fixtures/f1_result_fail.json'
import { nextPollDelay, retainUnchangedRuns } from './polling'
import type { Run } from './types'

const run = (run_id: string, result: unknown = null): Run =>
  ({ run_id, status: result ? 'complete' : 'running', created_at: 1, scenario, result, rerun_of: null }) as unknown as Run

describe('nextPollDelay', () => {
  it('polls at the normal cadence after success and after the first outage', () => {
    expect(nextPollDelay(0)).toBe(2_000)
    expect(nextPollDelay(1)).toBe(2_000)
  })

  it('backs off subsequent failures and caps the wait at thirty seconds', () => {
    expect(nextPollDelay(2)).toBe(4_000)
    expect(nextPollDelay(3)).toBe(8_000)
    expect(nextPollDelay(20)).toBe(30_000)
  })
})

describe('retainUnchangedRuns', () => {
  it('keeps the existing reference when polled data is identical', () => {
    const current = [run('run_1', fail)]
    const cloned = [run('run_1', structuredClone(fail))]
    expect(retainUnchangedRuns(current, cloned)).toBe(current)
  })

  it('replaces the reference when a run completes or arrives', () => {
    const current = [run('run_1', null)]
    const completed = [run('run_1', fail)]
    const added = [run('run_1', null), run('run_2', null)]
    expect(retainUnchangedRuns(current, completed)).toBe(completed)
    expect(retainUnchangedRuns(current, added)).toBe(added)
  })
})
