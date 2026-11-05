import { useEffect, useMemo, useRef, useState } from 'react'
import { listRuns } from '../api'
import { faultLabel, shortId } from '../format'
import { nextPollDelay } from '../polling'
import type { Run } from '../types'
import './HomePage.css'

type RunsState = 'loading' | 'ready' | 'offline'
type HomeTheme = 'light' | 'dark'
type TerminalTone = 'command' | 'output' | 'comment' | 'fail' | 'pass'
type TerminalLine = { tone: TerminalTone; text: string }

const HOME_TERMINAL_LINES: TerminalLine[] = [
  { tone: 'command', text: '$ python -m cli run F1\n' },
  { tone: 'output', text: 'Run f17355f6   F1 Lost capture response\n' },
  { tone: 'output', text: 'PayPal   1 capture     38.97 USD\n' },
  { tone: 'output', text: 'Your app 0 captures   0.00 USD\n' },
  { tone: 'fail', text: 'Verdict: FAIL\n\n' },
  { tone: 'comment', text: '# the AI proposes a fix, the code checks it\n' },
  { tone: 'command', text: '$ python -m cli run F1\n' },
  { tone: 'output', text: 'Run 90dc1d00   F1 Lost capture response\n' },
  { tone: 'output', text: 'PayPal   1 capture     38.97 USD\n' },
  { tone: 'output', text: 'Your app 1 capture   38.97 USD\n' },
  { tone: 'pass', text: 'Verdict: PASS' },
]

function initialHomeTheme(): HomeTheme {
  try {
    const savedTheme = window.localStorage.getItem('dg-theme')
    if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme
  } catch {
    // Theme preference remains usable when browser storage is unavailable.
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function appCaptureText(run: Run): string {
  const appCaptures = run.result?.observed.app_recorded_captures
  if (appCaptures == null) return 'No reading'
  return `${appCaptures} ${appCaptures === 1 ? 'capture' : 'captures'}`
}

function paypalCaptureText(run: Run): string {
  const captures = run.result?.observed.captures
  if (captures == null) return 'No reading'
  return `${captures} ${captures === 1 ? 'capture' : 'captures'}`
}

function gapText(run: Run): string {
  if (!run.result) return '—'
  const appCaptures = run.result.observed.app_recorded_captures
  if (appCaptures == null) return 'No reading'
  if (appCaptures === run.result.observed.captures) return `0.00 ${run.scenario.expect.currency}`
  return run.result.money_impact || `${run.result.observed.amount_captured} ${run.scenario.expect.currency}`
}

function HomeTerminal() {
  const [visibleLines, setVisibleLines] = useState<TerminalLine[]>([])

  useEffect(() => {
    let cancelled = false
    const timers = new Set<number>()
    const schedule = (callback: () => void, delay: number) => {
      const timer = window.setTimeout(() => {
        timers.delete(timer)
        if (!cancelled) callback()
      }, delay)
      timers.add(timer)
    }

    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setVisibleLines(HOME_TERMINAL_LINES)
      return () => { cancelled = true }
    }

    let lineIndex = 0
    const showNextLine = () => {
      if (cancelled) return
      if (lineIndex >= HOME_TERMINAL_LINES.length) {
        schedule(() => {
          lineIndex = 0
          setVisibleLines([])
          showNextLine()
        }, 2000)
        return
      }

      const line = HOME_TERMINAL_LINES[lineIndex]
      const currentIndex = lineIndex
      lineIndex += 1
      setVisibleLines((visible) => [...visible, { ...line, text: '' }])
      let charsShown = 0
      const typeNextCharacters = () => {
        if (cancelled) return
        charsShown += 2
        setVisibleLines((visible) => visible.map((entry, index) =>
          index === currentIndex ? { ...entry, text: line.text.slice(0, charsShown) } : entry,
        ))
        if (charsShown < line.text.length) {
          schedule(typeNextCharacters, 16)
        } else {
          schedule(showNextLine, line.tone === 'command' || line.tone === 'comment' ? 120 : 260)
        }
      }
      typeNextCharacters()
    }

    setVisibleLines([])
    showNextLine()
    return () => {
      cancelled = true
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [])

  return (
    <aside className="home-terminal" aria-label="Latest run evidence">
      <div className="home-terminal-head">
        <span className="terminal-lights" aria-hidden="true"><i /><i /><i /></span>
        <h2>Terminal</h2>
      </div>
      <pre className="home-terminal-content" aria-live="off" aria-label="Latest run evidence">
        {visibleLines.map((line, index) => (
          <span key={`${index}-${line.tone}`} className={`terminal-${line.tone}`}>{line.text}</span>
        ))}
      </pre>
    </aside>
  )
}

export function HomePage() {
  const breakWordRef = useRef<HTMLSpanElement>(null)
  const [theme, setTheme] = useState<HomeTheme>(initialHomeTheme)
  const [runs, setRuns] = useState<Run[]>([])
  const [runsState, setRunsState] = useState<RunsState>('loading')

  useEffect(() => {
    try {
      window.localStorage.setItem('dg-theme', theme)
    } catch {
      // The theme still applies for this visit without persistent storage.
    }
  }, [theme])

  useEffect(() => {
    const breakWord = breakWordRef.current
    if (!breakWord || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

    let resetTimer: number | undefined
    const glitch = () => {
      breakWord.classList.remove('go')
      void breakWord.offsetWidth
      breakWord.classList.add('go')
      if (resetTimer != null) window.clearTimeout(resetTimer)
      resetTimer = window.setTimeout(() => breakWord.classList.remove('go'), 950)
    }
    const initialTimer = window.setTimeout(glitch, 500)
    const repeatTimer = window.setInterval(glitch, 7000)
    breakWord.addEventListener('mouseenter', glitch)

    return () => {
      window.clearTimeout(initialTimer)
      window.clearInterval(repeatTimer)
      if (resetTimer != null) window.clearTimeout(resetTimer)
      breakWord.removeEventListener('mouseenter', glitch)
    }
  }, [])

  useEffect(() => {
    let active = true
    let inFlight = false
    let failures = 0
    let timer: number | undefined

    const pollRuns = async () => {
      if (!active || inFlight) return
      if (document.visibilityState === 'hidden') {
        timer = window.setTimeout(() => void pollRuns(), 5000)
        return
      }

      inFlight = true
      try {
        const nextRuns = await listRuns()
        if (!active) return
        setRuns(nextRuns)
        setRunsState('ready')
        failures = 0
      } catch {
        if (active) {
          setRunsState('offline')
          failures += 1
        }
      } finally {
        inFlight = false
      }

      if (active) timer = window.setTimeout(() => void pollRuns(), nextPollDelay(failures))
    }

    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return
      if (timer !== undefined) window.clearTimeout(timer)
      timer = undefined
      void pollRuns()
    }

    void pollRuns()
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      active = false
      if (timer !== undefined) window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  const latestRuns = useMemo(
    () => [...runs].sort((a, b) => b.created_at - a.created_at).slice(0, 4),
    [runs],
  )
  const latestFailedRun = latestRuns.find((run) => run.result?.verdict === 'FAIL')

  return (
    <div className="home-page" data-theme={theme}>
      <header className="home-header">
        <a className="home-brand" href="/" aria-label="DriftGuard home">DriftGuard</a>
        <nav className="home-nav" aria-label="Main navigation">
          <a href="/live/overview">Overview</a>
          <a href="/live/runs">Runs</a>
          <a href="/live/faults">Faults</a>
          <a href="/live/studio">Studio</a>
          <a href="/live/docs">Docs</a>
        </nav>
        <span className="home-header-spacer" />
        <a className="home-ask" href="/live/studio">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true">
            <path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z" />
          </svg>
          Ask Studio
        </a>
        <button
          className="home-mode-button"
          type="button"
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          onClick={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')}
        >
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
        <a className="home-button home-button-primary home-header-cta" href="/live/overview">
          Open dashboard
        </a>
      </header>

      <main>
        <section className="home-hero" id="overview" aria-labelledby="home-title">
          <div className="home-copy">
            <h1 id="home-title">
              <span className="home-glitch" ref={breakWordRef}>
                Break
                <span className="home-glitch-layer home-glitch-l1" aria-hidden="true">Break</span>
                <span className="home-glitch-layer home-glitch-l2" aria-hidden="true">Break</span>
                <span className="home-glitch-layer home-glitch-l3" aria-hidden="true">Break</span>
              </span>{' '}
              your checkout before your customers do.
            </h1>
            <p className="home-lede">
              DriftGuard breaks a PayPal sandbox checkout on purpose, compares PayPal&apos;s
              records with your app&apos;s, and proves the fix with the same test.
            </p>
            <div className="home-actions">
              <a className="home-button home-button-primary" href="/live/overview">Open the dashboard</a>
              <a
                className="home-button home-button-secondary"
                href={latestFailedRun
                  ? `/live/runs/${encodeURIComponent(latestFailedRun.run_id)}`
                  : '/live/runs'}
              >
                Read a failed run
              </a>
            </div>
          </div>
          <HomeTerminal />
        </section>

        <section className="home-band" id="latest-runs" aria-labelledby="latest-runs-title">
          <h2 id="latest-runs-title">Latest runs</h2>
          <div className="home-runs-scroll">
            <table className="home-runs-table">
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Verdict</th>
                  <th scope="col">Fault</th>
                  <th scope="col">PayPal recorded</th>
                  <th scope="col">App recorded</th>
                  <th scope="col">Gap</th>
                </tr>
              </thead>
              <tbody>
                {runsState === 'loading' ? (
                  <tr><td colSpan={6} className="home-table-message">Loading runs…</td></tr>
                ) : runsState === 'offline' ? (
                  <tr><td colSpan={6} className="home-table-message">Can&apos;t reach the API. Start the engine or mock runner to show recent runs.</td></tr>
                ) : latestRuns.length === 0 ? (
                  <tr><td colSpan={6} className="home-table-message">No runs yet. Launch a test from the live dashboard to see results here.</td></tr>
                ) : latestRuns.map((run) => {
                  const verdict = run.result?.verdict ?? 'RUNNING'
                  const appCaptures = run.result?.observed.app_recorded_captures
                  return (
                    <tr key={run.run_id}>
                      <td className="home-run-id"><a href={`/live/runs/${encodeURIComponent(run.run_id)}`}>{shortId(run.run_id)}</a></td>
                      <td><span className={`home-verdict home-verdict-${verdict.toLowerCase()}`}>{verdict}</span></td>
                      <td>{faultLabel(run.scenario.fault)}</td>
                      <td>{paypalCaptureText(run)}</td>
                      <td>{appCaptures == null ? 'No reading' : appCaptureText(run)}</td>
                      <td className="home-gap">{gapText(run)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {runsState === 'ready' && (
              <div className="home-runs-footer">
                <span>{latestRuns.length} recent {latestRuns.length === 1 ? 'run' : 'runs'}</span>
                <span>{runs.length} total</span>
              </div>
            )}
          </div>
          <div className="home-cols3" id="how-it-works">
            <div>
              <b>Break</b>
              <p>Drops a reply, forces a decline, replays a webhook. One fault at a time.</p>
            </div>
            <div>
              <b>Compare</b>
              <p>Asks PayPal what happened, then checks what your app recorded.</p>
            </div>
            <div>
              <b>Fix and prove</b>
              <p>AI proposes a small change, code checks it, and the same test runs again.</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
