import type { FixProposal, Run } from './types'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
// The AI service holds the model key; the browser only ever talks to it.
export const AI_URL: string = import.meta.env.VITE_AI_URL ?? 'http://localhost:8001'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init)
  if (!res.ok) {
    let message = `${init?.method ?? 'GET'} ${path} failed (${res.status})`
    try {
      const body = (await res.json()) as { detail?: unknown; message?: unknown; error?: unknown }
      if (typeof body.detail === 'string') {
        message = body.detail
      } else if (Array.isArray(body.detail)) {
        message = body.detail
          .map((d: unknown) =>
            typeof d === 'object' && d !== null && 'msg' in d ? String((d as { msg: unknown }).msg) : String(d),
          )
          .join('; ')
      } else if (body.detail) {
        message = typeof body.detail === 'object' ? JSON.stringify(body.detail) : String(body.detail)
      } else if (typeof body.message === 'string') {
        message = body.message
      } else if (typeof body.error === 'string') {
        message = body.error
      }
    } catch {
      /* keep the generic message */
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export const listRuns = (): Promise<Run[]> => request<Run[]>('/runs')
export const launchRun = (fault?: string): Promise<Run> =>
  request<Run>('/runs', {
    method: 'POST',
    ...(fault
      ? {
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fault }),
        }
      : {}),
  })
export const rerunRun = (runId: string): Promise<Run> =>
  request<Run>(`/runs/${runId}/rerun`, { method: 'POST' })
export const verifyFixRun = (runId: string): Promise<Run> =>
  request<Run>(`/runs/${runId}/verify-fix`, { method: 'POST' })

/** Ask the Fixer for a patch for a failing run. Nothing is applied: the answer is a checked diff. */
export async function proposeFix(run: Run): Promise<FixProposal> {
  let res: Response
  try {
    res = await fetch(`${AI_URL}/fix`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario: run.scenario, result: run.result }),
    })
  } catch {
    throw new Error(`Could not reach the AI service at ${AI_URL}. Is it running?`)
  }
  if (!res.ok) {
    let detail = `The AI service answered HTTP ${res.status}`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* keep the generic message */
    }
    throw new Error(detail)
  }
  return (await res.json()) as FixProposal
}
