import { Component, lazy, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Run } from '../types'
import { BeforeAfter } from './BeforeAfter'
import { EvidenceDrawer } from './EvidenceDrawer'
import { DocsPage, FaultsPage, OverviewPage, RunDetailPage, RunsPage } from './LivePages'
import { LiveDashboardLayout } from './LiveDashboardLayout'
import type { LiveView } from '../routing'
import { originalOf, rerunOf } from '../beforeAfter'
import { useDashboardRuns } from '../hooks/useDashboardRuns'
import '../beforeAfter.css'
import './LivePages.css'

const StudioPanel = lazy(() => import('./StudioPanel'))

type LiveTheme = 'light' | 'dark'

function initialLiveTheme(): LiveTheme {
  try {
    const savedTheme = window.localStorage.getItem('dg-theme')
    if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme
  } catch {
    // Use the operating system preference if storage is unavailable.
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** AG Studio is an add-on view: if it fails to load, the run pages remain usable. */
class StudioBoundary extends Component<{ children: ReactNode }, { failed: string | null }> {
  state = { failed: null as string | null }
  static getDerivedStateFromError(error: unknown) {
    return { failed: error instanceof Error ? error.message : 'unknown error' }
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

export default function LiveDashboard({ view, runId }: { view: LiveView; runId: string | null }) {
  const {
    actionError,
    busy,
    dismissActionError,
    fixes,
    launch,
    loaded,
    offline,
    propose,
    reconnected,
    rerun,
    verify,
    runs,
  } = useDashboardRuns()
  const [selectedId, setSelectedId] = useState<string | null>(runId)
  const [theme, setTheme] = useState<LiveTheme>(initialLiveTheme)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem('dg-sidebar-collapsed') === 'true'
    } catch {
      return false
    }
  })
  const [compareBeforeId, setCompareBeforeId] = useState<string | null>(null)
  const [compareAfterId, setCompareAfterId] = useState<string | null>(null)
  const evidenceReturnFocus = useRef<HTMLElement | null>(null)

  const selected = useMemo(() => runs.find((run) => run.run_id === selectedId) ?? null, [runs, selectedId])
  const compareBefore = useMemo(() => runs.find((run) => run.run_id === compareBeforeId) ?? null, [runs, compareBeforeId])
  const compareAfter = compareAfterId
    ? runs.find((run) => run.run_id === compareAfterId)
    : compareBefore ? rerunOf(runs, compareBefore.run_id) : undefined
  const drawerOpen = selected !== null && view !== 'run'

  useEffect(() => {
    try {
      window.localStorage.setItem('dg-theme', theme)
    } catch {
      // The theme still applies for this visit without persistent storage.
    }
  }, [theme])

  useEffect(() => {
    try {
      window.localStorage.setItem('dg-sidebar-collapsed', String(sidebarCollapsed))
    } catch {
      // The sidebar still works for this visit without persistent storage.
    }
  }, [sidebarCollapsed])

  const openEvidence = (runId: string, opener?: HTMLElement) => {
    evidenceReturnFocus.current = opener ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null)
    setSelectedId(runId)
  }

  const runActionAndOpen = async (action: () => Promise<Run | undefined>) => {
    evidenceReturnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const run = await action()
    if (run) setSelectedId(run.run_id)
    return run
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

  const rerunAndCompare = async (runId: string) => {
    const failed = runs.find((run) => run.run_id === runId)?.result?.verdict === 'FAIL'
    const rerunResult = await runActionAndOpen(() => failed ? verify(runId) : rerun(runId))
    if (rerunResult) {
      setCompareBeforeId(runId)
      setCompareAfterId(rerunResult.run_id)
    }
  }

  const compareFor = (run: Run): { label: string; open: () => void } | null => {
    const original = originalOf(runs, run)
    if (original) return { label: 'See before and after', open: () => { setCompareBeforeId(original.run_id); setCompareAfterId(run.run_id) } }
    const child = rerunOf(runs, run.run_id)
    if (child) return { label: 'See before and after', open: () => { setCompareBeforeId(run.run_id); setCompareAfterId(child.run_id) } }
    return null
  }

  return (
    <div className={`app s02-live ${drawerOpen ? 'with-drawer' : ''}`} data-theme={theme}>
      <LiveDashboardLayout
        actionError={actionError}
        busy={busy}
        hasRuns={runs.length > 0}
        offline={offline}
        onDismissActionError={dismissActionError}
        onLaunch={() => { void runActionAndOpen(launch) }}
        onToggleSidebar={() => setSidebarCollapsed((collapsed) => !collapsed)}
        onToggleTheme={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')}
        reconnected={reconnected}
        sidebarCollapsed={sidebarCollapsed}
        theme={theme}
        view={view}
      >
        {view === 'studio' ? (
          <StudioBoundary>
            <Suspense fallback={<p className="muted">Loading Studio…</p>}>
              <StudioPanel runs={runs} />
            </Suspense>
          </StudioBoundary>
        ) : view === 'overview' ? (
          <OverviewPage runs={runs} loading={!loaded} offline={offline} selectedId={selectedId} onSelect={openEvidence} />
        ) : view === 'faults' ? (
          <FaultsPage runs={runs} loading={!loaded} offline={offline} selectedId={selectedId} onSelect={openEvidence} />
        ) : view === 'docs' ? (
          <DocsPage />
        ) : view === 'run' ? (
          <RunDetailPage
            run={selected}
            runs={runs}
            loading={!loaded}
            offline={offline}
            busy={busy}
            fix={selected ? fixes[selected.run_id] : undefined}
            onBack={() => { window.location.href = '/live/runs' }}
            onRerun={(runId) => void rerunAndCompare(runId)}
            onPropose={() => { if (selected) void propose(selected) }}
          />
        ) : (
          <RunsPage runs={runs} loading={!loaded} offline={offline} selectedId={selectedId} onSelect={openEvidence} />
        )}
      </LiveDashboardLayout>

      {selected && view !== 'run' && (
        <EvidenceDrawer
          run={selected}
          busy={busy}
          fix={fixes[selected.run_id]}
          compare={compareFor(selected)}
          onClose={closeEvidence}
          onRerun={(runId) => void rerunAndCompare(runId)}
          onPropose={() => void propose(selected)}
        />
      )}

      {compareBefore && (
        <BeforeAfter
          before={compareBefore}
          after={compareAfter}
          proposal={compareAfter?.fix?.proposal}
          onClose={() => setCompareBeforeId(null)}
        />
      )}
    </div>
  )
}
