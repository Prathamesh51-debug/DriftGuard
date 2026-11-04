import { describe, expect, it } from 'vitest'
import { nextPollDelay } from './polling'

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
