import { useCallback, useEffect, useRef, useState } from 'react'
import { launchRun, listRuns, proposeFix, rerunRun } from '../api'
import { nextPollDelay } from '../polling'
import type { FixState, Run } from '../types'

export function useDashboardRuns() {
  const [runs, setRuns] = useState<Run[]>([])
  const [offline, setOffline] = useState(false)
  const [reconnected, setReconnected] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [fixes, setFixes] = useState<Record<string, FixState>>({})
  const wasOffline = useRef(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

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

  const runAction = useCallback(async (action: () => Promise<Run>): Promise<Run | undefined> => {
    setBusy(true)
    setActionError(null)
    try {
      const run = await action()
      await refresh()
      return run
    } catch (error) {
      setActionError(`Couldn't start that: ${error instanceof Error ? error.message : 'request failed'}`)
      return undefined
    } finally {
      setBusy(false)
    }
  }, [refresh])

  const launch = useCallback(() => runAction(launchRun), [runAction])
  const rerun = useCallback((runId: string) => runAction(() => rerunRun(runId)), [runAction])

  const propose = useCallback(async (run: Run) => {
    setFixes((current) => ({ ...current, [run.run_id]: { status: 'loading' } }))
    try {
      const proposal = await proposeFix(run)
      setFixes((current) => ({ ...current, [run.run_id]: { status: 'ready', proposal } }))
    } catch (error) {
      setFixes((current) => ({
        ...current,
        [run.run_id]: { status: 'error', message: error instanceof Error ? error.message : 'The request failed' },
      }))
    }
  }, [])

  return {
    actionError,
    busy,
    dismissActionError: () => setActionError(null),
    fixes,
    launch,
    loaded,
    offline,
    propose,
    refresh,
    reconnected,
    rerun,
    runs,
  }
}
