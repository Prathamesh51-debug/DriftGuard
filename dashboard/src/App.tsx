import { useCallback, useEffect, useMemo, useState } from 'react'
import { API_URL, launchRun, listRuns, rerunRun } from './api'
import type { Run } from './types'
import { RunsGrid } from './components/RunsGrid'
import { EvidenceDrawer } from './components/EvidenceDrawer'
import './App.css'

export default function App() {
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setRuns(await listRuns())
      setError(null)
    } catch {
      setError(`Can't reach the engine at ${API_URL}. Is the mock runner running?`)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = setInterval(() => void refresh(), 1000)
    return () => clearInterval(timer)
  }, [refresh])

  const act = async (fn: () => Promise<Run>) => {
    setBusy(true)
    try {
      const run = await fn()
      setSelectedId(run.run_id)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  const selected = useMemo(() => runs.find((r) => r.run_id === selectedId) ?? null, [runs, selectedId])
  const failing = runs.filter((r) => r.result?.verdict === 'FAIL').length
  const passing = runs.filter((r) => r.result?.verdict === 'PASS').length

  return (
    <div className={`app ${selected ? 'with-drawer' : ''}`}>
      <header className="topbar">
        <div>
          <h1>DriftGuard</h1>
          <p className="muted">Chaos runs checked against PayPal&apos;s own records</p>
        </div>
        <div className="topbar-right">
          <div className="tally" aria-label="Run totals">
            <span className="bad">{failing} red</span>
            <span className="good">{passing} green</span>
          </div>
          <button className="btn btn-primary" disabled={busy} onClick={() => void act(launchRun)}>
            Launch F1 run
          </button>
        </div>
      </header>

      {error && (
        <div className="banner" role="alert">
          {error}
        </div>
      )}

      <main className="main">
        <RunsGrid runs={runs} selectedId={selectedId} onSelect={setSelectedId} />
      </main>

      {selected && (
        <EvidenceDrawer
          run={selected}
          busy={busy}
          onClose={() => setSelectedId(null)}
          onRerun={(id) => void act(() => rerunRun(id))}
        />
      )}
    </div>
  )
}
