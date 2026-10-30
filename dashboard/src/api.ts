import type { Run } from './types'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init)
  if (!res.ok) throw new Error(`${init?.method ?? 'GET'} ${path} failed (${res.status})`)
  return res.json() as Promise<T>
}

export const listRuns = (): Promise<Run[]> => request<Run[]>('/runs')
export const launchRun = (): Promise<Run> => request<Run>('/runs', { method: 'POST' })
export const rerunRun = (runId: string): Promise<Run> =>
  request<Run>(`/runs/${runId}/rerun`, { method: 'POST' })
