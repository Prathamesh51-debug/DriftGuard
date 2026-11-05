export type DashboardSurface = 'home' | 'live' | 'not-found'
export type LiveView = 'overview' | 'runs' | 'run' | 'faults' | 'studio' | 'docs'

export type DashboardRoute =
  | { surface: 'home' }
  | { surface: 'live'; view: LiveView; runId: string | null }
  | { surface: 'not-found' }

export function dashboardSurface(pathname: string): DashboardSurface {
  const normalized = pathname.replace(/\/+$/, '') || '/'
  if (normalized === '/') return 'home'
  if (normalized === '/live' || normalized.startsWith('/live/')) return 'live'
  return 'not-found'
}

export function initialLiveView(search: string): LiveView {
  const requested = new URLSearchParams(search).get('view')
  if (requested === 'overview' || requested === 'runs' || requested === 'run' || requested === 'faults' || requested === 'studio' || requested === 'docs') {
    return requested
  }
  return 'runs'
}

function decodeRunId(value: string): string | null {
  try {
    return decodeURIComponent(value)
  } catch {
    return null
  }
}

/** Resolve a browser URL to a page while keeping the old query links working. */
export function resolveDashboardRoute(pathname: string, search: string): DashboardRoute {
  const normalized = pathname.replace(/\/+$/, '') || '/'
  if (normalized === '/') return { surface: 'home' }
  if (normalized === '/live') {
    const params = new URLSearchParams(search)
    const view = initialLiveView(search)
    const runId = params.get('run')
    return {
      surface: 'live',
      view,
      runId: view === 'run' ? runId : null,
    }
  }

  const detailMatch = normalized.match(/^\/live\/runs\/([^/]+)$/)
  if (detailMatch) {
    const runId = decodeRunId(detailMatch[1])
    return runId
      ? { surface: 'live', view: 'run', runId }
      : { surface: 'not-found' }
  }

  const views: Record<string, LiveView> = {
    '/live/overview': 'overview',
    '/live/runs': 'runs',
    '/live/faults': 'faults',
    '/live/studio': 'studio',
    '/live/docs': 'docs',
  }
  const view = views[normalized]
  return view
    ? { surface: 'live', view, runId: null }
    : { surface: 'not-found' }
}
