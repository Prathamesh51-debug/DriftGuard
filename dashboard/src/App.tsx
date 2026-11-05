import { HomePage } from './components/HomePage'
import LiveDashboard from './components/LiveDashboard'
import { resolveDashboardRoute } from './routing'
import './App.css'

export default function App() {
  const route = resolveDashboardRoute(window.location.pathname, window.location.search)
  if (route.surface === 'home') return <HomePage />
  if (route.surface === 'live') return <LiveDashboard view={route.view} runId={route.runId} />

  return (
    <main className="route-missing">
      <h1>This DriftGuard page doesn&apos;t exist.</h1>
      <p>Choose a DriftGuard page.</p>
      <p><a href="/">Home</a><a href="/live">Open live dashboard</a></p>
    </main>
  )
}
