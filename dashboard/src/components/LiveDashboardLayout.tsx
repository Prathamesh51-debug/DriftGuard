import type { ReactNode } from 'react'
import { API_URL } from '../api'
import type { LiveView } from '../routing'

type LiveTheme = 'light' | 'dark'
type SidebarIconName = 'overview' | 'runs' | 'faults' | 'studio' | 'docs'

interface LiveDashboardLayoutProps {
  actionError: string | null
  busy: boolean
  children: ReactNode
  hasRuns: boolean
  offline: boolean
  onDismissActionError: () => void
  onLaunch: () => void
  onToggleSidebar: () => void
  onToggleTheme: () => void
  reconnected: boolean
  sidebarCollapsed: boolean
  theme: LiveTheme
  view: LiveView
}

function SidebarIcon({ name }: { name: SidebarIconName }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

  return (
    <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" {...common}>
      {name === 'overview' && <><rect x="3" y="3" width="5.5" height="5.5" rx="1" /><rect x="11.5" y="3" width="5.5" height="5.5" rx="1" /><rect x="3" y="11.5" width="5.5" height="5.5" rx="1" /><rect x="11.5" y="11.5" width="5.5" height="5.5" rx="1" /></>}
      {name === 'runs' && <><circle cx="4" cy="5" r=".8" /><circle cx="4" cy="10" r=".8" /><circle cx="4" cy="15" r=".8" /><path d="M7 5h10M7 10h10M7 15h10" /></>}
      {name === 'faults' && <><path d="M10 3 18 17H2L10 3Z" /><path d="M10 8v4M10 14.5h.01" /></>}
      {name === 'studio' && <><path d="M3 4.5h14v9H9l-4 3v-3H3z" /><path d="M6.5 8h7M6.5 10.5h4.5" /></>}
      {name === 'docs' && <><path d="M4 3.5h8.5A2.5 2.5 0 0 1 15 6v10.5H6.5A2.5 2.5 0 0 1 4 14V3.5Z" /><path d="M4 14a2.5 2.5 0 0 1 2.5-2.5H15M8 7h4" /></>}
    </svg>
  )
}

export function LiveDashboardLayout({
  actionError,
  busy,
  children,
  hasRuns,
  offline,
  onDismissActionError,
  onLaunch,
  onToggleSidebar,
  onToggleTheme,
  reconnected,
  sidebarCollapsed,
  theme,
  view,
}: LiveDashboardLayoutProps) {
  const showBanners = offline || reconnected || actionError !== null

  return (
    <>
      <header className="topbar s02-header">
        <a className="s02-brand" href="/">DriftGuard</a>
        <span className="s02-header-spacer" />
        <a className="s02-ask" href="/live/studio">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true">
            <path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z" />
          </svg>
          Ask Studio
        </a>
        <button
          className="s02-mode-button"
          type="button"
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          onClick={onToggleTheme}
        >
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
        <button
          className="btn btn-primary s02-launch"
          disabled={busy || offline}
          title={offline ? 'The engine is unreachable' : undefined}
          onClick={onLaunch}
        >
          {busy ? 'Working…' : 'Launch F1 run'}
        </button>
      </header>

      {showBanners && (
        <div className="banners">
          {offline && (
            <div className="banner" role="alert">
              {hasRuns
                ? 'Connection lost. Showing the last known runs. Retrying automatically with backoff.'
                : `Can't reach the engine at ${API_URL}. Retrying automatically with backoff. Is the mock runner or engine running?`}
            </div>
          )}
          {reconnected && <div className="banner banner-ok" role="status">Reconnected to the engine.</div>}
          {actionError && (
            <div className="banner banner-error" role="alert">
              <span>{actionError}</span>
              <button className="link-btn" onClick={onDismissActionError}>Dismiss</button>
            </div>
          )}
        </div>
      )}

      <div className={`s02-workspace ${sidebarCollapsed ? 'is-sidebar-collapsed' : ''}`}>
        <nav className={`s02-sidebar ${sidebarCollapsed ? 'is-collapsed' : ''}`} id="dashboard-sidebar-nav" aria-label="Dashboard sections">
          <button
            className="s02-sidebar-toggle"
            type="button"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!sidebarCollapsed}
            aria-controls="dashboard-sidebar-nav"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={onToggleSidebar}
          >
            <svg className="s02-sidebar-toggle-icon" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={sidebarCollapsed ? 'm8 4 6 6-6 6' : 'm12 4-6 6 6 6'} />
            </svg>
            <span className="s02-sidebar-toggle-label">Collapse sidebar</span>
          </button>
          <small>Test</small>
          <a href="/live/overview" aria-current={view === 'overview' ? 'page' : undefined} title={sidebarCollapsed ? 'Overview' : undefined}>
            <SidebarIcon name="overview" /><span className="s02-sidebar-label">Overview</span>
          </a>
          <a href="/live/runs" aria-current={view === 'runs' || view === 'run' ? 'page' : undefined} title={sidebarCollapsed ? 'Runs' : undefined}>
            <SidebarIcon name="runs" /><span className="s02-sidebar-label">Runs</span>
          </a>
          <a href="/live/faults" aria-current={view === 'faults' ? 'page' : undefined} title={sidebarCollapsed ? 'Faults' : undefined}>
            <SidebarIcon name="faults" /><span className="s02-sidebar-label">Faults</span>
          </a>
          <small>Ask</small>
          <a href="/live/studio" aria-current={view === 'studio' ? 'page' : undefined} title={sidebarCollapsed ? 'Studio' : undefined}>
            <SidebarIcon name="studio" /><span className="s02-sidebar-label">Studio</span>
          </a>
          <small>Setup</small>
          <a href="/live/docs" aria-current={view === 'docs' ? 'page' : undefined} title={sidebarCollapsed ? 'Connect a shop' : undefined}>
            <SidebarIcon name="docs" /><span className="s02-sidebar-label">Connect a shop</span>
          </a>
        </nav>

        <main id="live-view-panel" className="main s02-main">{children}</main>
      </div>
    </>
  )
}
