import { Component, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react'
import { API_URL, launchRun, listRuns, proposeFix, rerunRun } from './api'
import type { FixState, Run } from './types'
import { RunsGrid } from './components/RunsGrid'
import { EvidenceDrawer } from './components/EvidenceDrawer'
import { BeforeAfter } from './components/BeforeAfter'
import { nextPollDelay } from './polling'
import { dashboardSurface, initialLiveView } from './routing'
import { originalOf, rerunOf } from './beforeAfter'
import './App.css'
import './beforeAfter.css'

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

function LiveDashboardApp() {
  const [runs, setRuns] = useState<Run[]>([])
  const [offline, setOffline] = useState(false)
  const [reconnected, setReconnected] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [view, setView] = useState<'runs' | 'studio'>(() => initialLiveView(window.location.search))
  const [fixes, setFixes] = useState<Record<string, FixState>>({})
  const [compareBeforeId, setCompareBeforeId] = useState<string | null>(null)
  const wasOffline = useRef(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const evidenceReturnFocus = useRef<HTMLElement | null>(null)

  const openEvidence = (runId: string, opener?: HTMLElement) => {
    evidenceReturnFocus.current = opener ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null)
    setSelectedId(runId)
  }

  const closeEvidence = () => {
    const closingRunId = selectedId
    setSelectedId(null)
    requestAnimationFrame(() => {
      const opener = evidenceReturnFocus.current
      if (opener?.isConnected) {
        opener.focus()
      } else if (closingRunId) {
        const fallback = document.getElementById(`mobile-run-${closingRunId}`)
          ?? document.querySelector<HTMLElement>('.desktop-run-grid .ag-cell')
        fallback?.focus()
      }
      evidenceReturnFocus.current = null
    })
  }

  const refresh = useCallback(async (): Promise<boolean> => {
    try {
      setRuns(await listRuns())
      setOffline(false)
      if (wasOffline.current) {
        wasOffline.current = false
        setReconnected(true)
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = setTimeout(() => setReconnected(false), 3000)
      }
      return true
    } catch {
      wasOffline.current = true
      setReconnected(false)
      setOffline(true)
      return false
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    let inFlight = false
    let failures = 0
    let timer: ReturnType<typeof setTimeout> | undefined

    const poll = async () => {
      if (cancelled || inFlight) return
      if (document.visibilityState === 'hidden') {
        timer = setTimeout(() => void poll(), 5000)
        return
      }

      inFlight = true
      const succeeded = await refresh()
      inFlight = false
      if (cancelled) return
      failures = succeeded ? 0 : failures + 1
      timer = setTimeout(() => void poll(), nextPollDelay(failures))
    }

    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return
      if (timer) clearTimeout(timer)
      timer = undefined
      void poll()
    }

    void poll()
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearTimeout(reconnectTimer.current)
    }
  }, [refresh])

  const onViewTabKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, current: 'runs' | 'studio') => {
    const next = event.key === 'ArrowRight' || event.key === 'ArrowDown'
      ? (current === 'runs' ? 'studio' : 'runs')
      : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
        ? (current === 'studio' ? 'runs' : 'studio')
        : event.key === 'Home'
          ? 'runs'
          : event.key === 'End'
            ? 'studio'
            : null
    if (!next) return
    event.preventDefault()
    setView(next)
    requestAnimationFrame(() => document.getElementById(`view-tab-${next}`)?.focus())
  }

  const act = async (fn: () => Promise<Run>): Promise<Run | undefined> => {
    evidenceReturnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setBusy(true)
    setActionError(null)
    try {
      const run = await fn()
      setSelectedId(run.run_id)
      await refresh()
      return run
    } catch (e) {
      setActionError(`Couldn't start that: ${e instanceof Error ? e.message : 'request failed'}`)
      return undefined
    } finally {
      setBusy(false)
    }
  }

  const propose = async (run: Run) => {
    setFixes((f) => ({ ...f, [run.run_id]: { status: 'loading' } }))
    try {
      const proposal = await proposeFix(run)
      setFixes((f) => ({ ...f, [run.run_id]: { status: 'ready', proposal } }))
    } catch (e) {
      setFixes((f) => ({ ...f, [run.run_id]: { status: 'error', message: e instanceof Error ? e.message : 'The request failed' } }))
    }
  }

  const rerunAndCompare = async (runId: string) => {
    const rerun = await act(() => rerunRun(runId))
    if (rerun) setCompareBeforeId(runId)
  }

  /** A before/after button for a run that has a re-run, or that is one. */
  const compareFor = (run: Run): { label: string; open: () => void } | null => {
    const original = originalOf(runs, run)
    if (original) return { label: 'See before and after', open: () => setCompareBeforeId(original.run_id) }
    if (rerunOf(runs, run.run_id)) return { label: 'See before and after', open: () => setCompareBeforeId(run.run_id) }
    return null
  }

  const selected = useMemo(() => runs.find((r) => r.run_id === selectedId) ?? null, [runs, selectedId])
  const compareBefore = useMemo(() => runs.find((r) => r.run_id === compareBeforeId) ?? null, [runs, compareBeforeId])
  const compareAfter = compareBefore ? rerunOf(runs, compareBefore.run_id) : undefined
  const compareFix = compareBeforeId ? fixes[compareBeforeId] : undefined
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
            <button
              key={v}
              id={`view-tab-${v}`}
              role="tab"
              aria-selected={view === v}
              aria-controls="live-view-panel"
              tabIndex={view === v ? 0 : -1}
              className={`tab ${view === v ? 'tab-on' : ''}`}
              onClick={() => setView(v)}
              onKeyDown={(event) => onViewTabKeyDown(event, v)}
            >
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
                ? 'Connection lost. Showing the last known runs. Retrying automatically with backoff.'
                : `Can't reach the engine at ${API_URL}. Retrying automatically with backoff. Is the mock runner or engine running?`}
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

      <main id="live-view-panel" className="main" role="tabpanel" aria-labelledby={`view-tab-${view}`} tabIndex={0}>
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
          onSelect={openEvidence}
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
          fix={fixes[selected.run_id]}
          compare={compareFor(selected)}
          onClose={closeEvidence}
          onRerun={(id) => void rerunAndCompare(id)}
          onPropose={() => void propose(selected)}
        />
      )}

      {compareBefore && (
        <BeforeAfter
          before={compareBefore}
          after={compareAfter}
          proposal={compareFix?.status === 'ready' ? compareFix.proposal : undefined}
          onClose={() => setCompareBeforeId(null)}
        />
      )}
    </div>
  )
}

export default function App() {
  const surface = dashboardSurface(window.location.pathname)
  if (surface === 'live') return <LiveDashboardApp />

  return (
    <main className="route-missing">
      <h1>This DriftGuard page doesn&apos;t exist.</h1>
      <p>Open the DriftGuard dashboard to view and run checks.</p>
      <p><a href="/">Open dashboard</a></p>
    </main>
  )
}
