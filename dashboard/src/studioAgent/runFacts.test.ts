import { describe, expect, it } from 'vitest'
import scenario from '../../../contracts/fixtures/f1_scenario.json'
import fail from '../../../contracts/fixtures/f1_result_fail.json'
import type { Run } from '../types'
import { describeRun, findRun, listRuns } from './runFacts'

const failed = { run_id: 'run_ab12cd34', status: 'complete', created_at: 1, scenario, result: fail, rerun_of: null } as unknown as Run
const running = { run_id: 'run_ee99ff00', status: 'running', created_at: 2, scenario, result: null, rerun_of: null } as unknown as Run

describe('findRun', () => {
  it('finds by full id, short id or case-insensitive suffix', () => {
    expect(findRun([failed, running], 'run_ab12cd34')).toBe(failed)
    expect(findRun([failed, running], 'ab12cd34')).toBe(failed)
    expect(findRun([failed, running], 'EE99')).toBeUndefined()
    expect(findRun([failed, running], '99ff00')).toBe(running)
  })
  it('does not match on an empty id', () => {
    expect(findRun([failed], '  ')).toBeUndefined()
  })
})

describe('describeRun', () => {
  it('states every fact from the stored result, including the app-vs-PayPal gap', () => {
    const text = describeRun(failed)
    expect(text).toContain('Verdict: FAIL')
    expect(text).toContain(`Rule checked: ${fail.rule}`)
    expect(text).toContain(fail.money_impact)
    expect(text).toContain(`The app itself recorded ${fail.observed.app_recorded_captures} capture(s)`)
    for (const id of [...fail.evidence.paypal_order_ids, ...fail.evidence.paypal_capture_ids]) expect(text).toContain(id)
  })
  it('says there is nothing to explain while a run is still going', () => {
    expect(describeRun(running)).toContain('No result yet')
  })
  it('never invents an app count when the record has none', () => {
    const noApp = { ...failed, result: { ...fail, observed: { ...fail.observed, app_recorded_captures: null } } } as unknown as Run
    expect(describeRun(noApp)).not.toContain('The app itself recorded')
  })
})

describe('listRuns', () => {
  it('lists one line per run with its verdict, or RUNNING', () => {
    const lines = listRuns([failed, running]).split('\n')
    expect(lines[0]).toContain('ab12cd34')
    expect(lines[0]).toContain('FAIL')
    expect(lines[1]).toContain('RUNNING')
  })
  it('handles no runs', () => {
    expect(listRuns([])).toBe('There are no runs yet.')
  })
})
