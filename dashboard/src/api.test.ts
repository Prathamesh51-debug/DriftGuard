import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { launchRun } from './api'

describe('launchRun', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('launches a default run without body when no fault is passed', async () => {
    let capturedUrl = ''
    let capturedInit: RequestInit | undefined
    globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      capturedUrl = String(url)
      capturedInit = init
      return new Response(JSON.stringify({ run_id: 'run_123', status: 'running' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    })

    const run = await launchRun()
    expect(capturedUrl).toContain('/runs')
    expect(capturedInit?.method).toBe('POST')
    expect(capturedInit?.body).toBeUndefined()
    expect(run.run_id).toBe('run_123')
  })

  it('sends fault in JSON body when fault parameter is provided', async () => {
    let capturedUrl = ''
    let capturedInit: RequestInit | undefined
    globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      capturedUrl = String(url)
      capturedInit = init
      return new Response(JSON.stringify({ run_id: 'run_456', status: 'running' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    })

    const run = await launchRun('F2_SLOW_PAYPAL')
    expect(capturedUrl).toContain('/runs')
    expect(capturedInit?.method).toBe('POST')
    expect(capturedInit?.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(capturedInit?.body as string)).toEqual({ fault: 'F2_SLOW_PAYPAL' })
    expect(run.run_id).toBe('run_456')
  })
})
