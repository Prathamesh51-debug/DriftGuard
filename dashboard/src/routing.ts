export type DashboardSurface = 'live' | 'not-found'
export type LiveView = 'runs' | 'studio'

export function dashboardSurface(pathname: string): DashboardSurface {
  const normalized = pathname.replace(/\/+$/, '') || '/'
  if (normalized === '/' || normalized === '/preview' || normalized === '/live' || normalized.startsWith('/live/')) return 'live'
  return 'not-found'
}

export function initialLiveView(search: string): LiveView {
  return new URLSearchParams(search).get('view') === 'studio' ? 'studio' : 'runs'
}
