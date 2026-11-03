import { Component, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { API_URL, launchRun, listRuns, rerunRun } from './api'
import type { Run } from './types'
import { RunsGrid } from './components/RunsGrid'
import { EvidenceDrawer } from './components/EvidenceDrawer'
import './App.css'

const StudioPanel = lazy(() => import('./components/StudioPanel'))

/** AG Studio is an add-on view: if it fails to load or render, the runs matrix must keep working. */
class StudioBoundary extends Component<{ children: ReactNode }, { failed: string | null }> {
  state = { failed: null as string | null }
  static getDerivedStateFromError(e: unknown) {
    return { failed: e instanceof Error ? e.message : 'unknown error' }
  }
  render() {
    return this.state.failed ? (
      <div className="notice notice-error" role="alert">
        <strong>The Studio view could not load</strong>
        <p>{this.state.failed}</p>
        <p className="muted small">The runs table is unaffected.</p>
      </div>
    ) : (
      this.props.children
    )
  }
}

export default function App() {
  const [runs, setRuns] = useState<Run[]>([])
  const [offline, setOffline] = useState(false)
  const [reconnected, setReconnected] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [view, setView] = useState<'runs' | 'studio'>('runs')
  const wasOffline = useRef(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const refresh = useCallback(async () => {
    try {
      setRuns(await listRuns())
      setOffline(false)
      if (wasOffline.current) {
        wasOffline.current = false
        setReconnected(true)
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = setTimeout(() => setReconnected(false), 3000)
      }
    } catch {
      wasOffline.current = true
      setReconnected(false)
      setOffline(true)
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = setInterval(() => void refresh(), 1000)
    return () => {
      clearInterval(timer)
      clearTimeout(reconnectTimer.current)
    }
  }, [refresh])

  const act = async (fn: () => Promise<Run>) => {
    setBusy(true)
    setActionError(null)
    try {
      const run = await fn()
      setSelectedId(run.run_id)
      await refresh()
    } catch (e) {
      setActionError(`Couldn't start that: ${e instanceof Error ? e.message : 'request failed'}`)
    } finally {
      setBusy(false)
    }
  }

  const selected = useMemo(() => runs.find((r) => r.run_id === selectedId) ?? null, [runs, selectedId])
  const failing = runs.filter((r) => r.result?.verdict === 'FAIL').length
  const passing = runs.filter((r) => r.result?.verdict === 'PASS').length
  const showBanners = offline || reconnected || actionError !== null

  return (
    <div className={`app ${selected ? 'with-drawer' : ''}`}>
      <header className="topbar">
        <div>
          <h1>DriftGuard</h1>
          <p className="muted">Chaos runs checked against PayPal&apos;s own records</p>
        </div>
        <div className="topbar-right">
          <div className="tabs" role="tablist" aria-label="View">
            {(['runs', 'studio'] as const).map((v) => (
              <button key={v} role="tab" aria-selected={view === v} className={`tab ${view === v ? 'tab-on' : ''}`} onClick={() => setView(v)}>
                {v === 'runs' ? 'Runs' : 'Studio'}
              </button>
            ))}
          </div>
          <div className="tally" aria-label="Run totals">
            <span className="bad">{failing} red</span>
            <span className="good">{passing} green</span>
          </div>
          <button
            className="btn btn-primary"
            disabled={busy || offline}
            title={offline ? 'The engine is unreachable' : undefined}
            onClick={() => void act(launchRun)}
          >
            {busy ? 'Working…' : 'Launch F1 run'}
          </button>
        </div>
      </header>

      {showBanners && (
        <div className="banners">
          {offline && (
            <div className="banner" role="alert">
              {runs.length > 0
                ? 'Connection lost. Showing the last known runs. Retrying every second.'
                : `Can't reach the engine at ${API_URL}. Retrying every second. Is the mock runner or engine running?`}
            </div>
          )}
          {reconnected && (
            <div className="banner banner-ok" role="status">
              Reconnected to the engine.
            </div>
          )}
          {actionError && (
            <div className="banner banner-error" role="alert">
              <span>{actionError}</span>
              <button className="link-btn" onClick={() => setActionError(null)}>
                Dismiss
              </button>
            </div>
          )}
        </div>
      )}

      <main className="main">
        {view === 'studio' ? (
          <StudioBoundary>
            <Suspense fallback={<p className="muted">Loading Studio…</p>}>
              <StudioPanel runs={runs} />
            </Suspense>
          </StudioBoundary>
        ) : (
        <RunsGrid
          runs={runs}
          selectedId={selectedId}
          onSelect={setSelectedId}
          loading={!loaded}
          emptyMessage={
            offline ? "Can't load runs while the engine is unreachable." : 'No runs yet. Click "Launch F1 run" to start one.'
          }
        />
        )}
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
