import { useEffect, useMemo, useRef } from 'react'
import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
  type ICellRendererParams,
} from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import type { Run } from '../types'
import { faultLabel, shortId, timeAgo } from '../format'
import { VerdictChip } from './VerdictChip'

ModuleRegistry.registerModules([AllCommunityModule])

const theme = themeQuartz.withParams({
  backgroundColor: '#12161c',
  foregroundColor: '#e6e9ee',
  headerBackgroundColor: '#171c24',
  headerTextColor: '#9aa4b2',
  borderColor: '#262d38',
  rowHoverColor: '#1a212b',
  selectedRowBackgroundColor: '#1e2a3a',
  accentColor: '#5b9dff',
  fontFamily: 'Inter, system-ui, sans-serif',
  fontSize: 13,
  headerFontWeight: 600,
  spacing: 7,
})

function EmptyOverlay({ message }: { message: string }) {
  return <span className="muted">{message}</span>
}

function gridCellFromEvent(event?: Event | null): HTMLElement | undefined {
  return event?.target instanceof HTMLElement
    ? event.target.closest<HTMLElement>('.ag-cell') ?? undefined
    : undefined
}

export function RunsGrid({
  runs,
  selectedId,
  onSelect,
  loading,
  emptyMessage,
}: {
  runs: Run[]
  selectedId: string | null
  onSelect: (runId: string, opener?: HTMLElement) => void
  loading: boolean
  emptyMessage: string
}) {
  const gridRef = useRef<AgGridReact<Run>>(null)

  // Row classes are computed once per row; redraw so the highlight follows the selection.
  useEffect(() => {
    gridRef.current?.api?.redrawRows()
  }, [selectedId])

  const columns = useMemo<ColDef<Run>[]>(
    () => [
      {
        headerName: 'Run',
        width: 150,
        cellClass: 'mono',
        valueGetter: (p) => (p.data ? shortId(p.data.run_id) : ''),
        cellRenderer: (p: ICellRendererParams<Run>) =>
          p.data ? (
            <span>
              {shortId(p.data.run_id)}
              {p.data.rerun_of && <span className="muted"> ↻ {shortId(p.data.rerun_of)}</span>}
            </span>
          ) : null,
      },
      {
        headerName: 'Fault',
        flex: 1.1,
        minWidth: 190,
        valueGetter: (p) => (p.data ? faultLabel(p.data.scenario.fault) : ''),
      },
      {
        headerName: 'Verdict',
        width: 130,
        cellRenderer: (p: ICellRendererParams<Run>) => (p.data ? <VerdictChip run={p.data} /> : null),
      },
      {
        headerName: 'Rule',
        flex: 1,
        minWidth: 200,
        cellClass: 'mono',
        valueGetter: (p) => p.data?.result?.rule ?? '—',
      },
      {
        headerName: 'Captures (PayPal / app)',
        width: 190,
        type: 'rightAligned',
        cellRenderer: (p: ICellRendererParams<Run>) => {
          const r = p.data?.result
          if (!p.data || !r) return <span className="muted">—</span>
          const paypal = r.observed.captures
          const app = r.observed.app_recorded_captures
          // The drift is PayPal's count versus the app's own record; fall back to the expected count when the app's is not reported.
          const compare = app ?? p.data.scenario.expect.captures_per_purchase
          return (
            <span className={`mono ${paypal !== compare ? 'bad' : ''}`}>
              {paypal} / {app ?? '?'}
            </span>
          )
        },
      },
      {
        headerName: 'Money impact',
        flex: 1.6,
        minWidth: 260,
        valueGetter: (p) => p.data?.result?.money_impact ?? 'waiting for PayPal ledger…',
      },
      {
        headerName: 'Started',
        width: 110,
        type: 'rightAligned',
        valueGetter: (p) => (p.data ? timeAgo(p.data.created_at) : ''),
      },
    ],
    [],
  )

  return (
    <div className="grid-wrap">
      <p id="run-grid-instructions" className="sr-only">
        Use the arrow keys to move through run results. Press Enter or Space to open evidence for a run.
      </p>
      <div className="desktop-run-grid" role="region" aria-label="Run results" aria-describedby="run-grid-instructions">
        <AgGridReact<Run>
          ref={gridRef}
          theme={theme}
          rowData={runs}
          columnDefs={columns}
          getRowId={(p) => p.data.run_id}
          onRowClicked={(e) => e.data && onSelect(e.data.run_id, gridCellFromEvent(e.event))}
          onCellKeyDown={(e) => {
            if (!e.data || !(e.event instanceof KeyboardEvent)) return
            if (e.event.key !== 'Enter' && e.event.key !== ' ') return
            e.event.preventDefault()
            onSelect(e.data.run_id, gridCellFromEvent(e.event))
          }}
          getRowClass={(p) => (p.data?.run_id === selectedId ? 'row-selected' : '')}
          loading={loading}
          noRowsOverlayComponent={EmptyOverlay}
          noRowsOverlayComponentParams={{ message: emptyMessage }}
        />
      </div>
      <section className="mobile-run-list" aria-label="Run results">
        {loading ? <p className="muted mobile-run-empty" role="status">Loading runs…</p> : runs.length === 0 ? (
          <p className="muted mobile-run-empty">{emptyMessage}</p>
        ) : runs.map((run) => {
          const verdict = run.result?.verdict ?? 'RUNNING'
          const appCaptures = run.result?.observed.app_recorded_captures
          return (
            <button
              key={run.run_id}
              id={`mobile-run-${run.run_id}`}
              className={`mobile-run-card ${selectedId === run.run_id ? 'is-selected' : ''}`}
              aria-label={`Open evidence for run ${shortId(run.run_id)}, ${verdict}, ${faultLabel(run.scenario.fault)}`}
              aria-pressed={selectedId === run.run_id}
              onClick={(event) => onSelect(run.run_id, event.currentTarget)}
            >
              <span className="mobile-run-head">
                <span className="mono">{shortId(run.run_id)}</span>
                <VerdictChip run={run} />
              </span>
              <span className="mobile-run-fault">{faultLabel(run.scenario.fault)}</span>
              <span className="mobile-run-meta">
                <span>{run.result?.money_impact ?? 'Waiting for PayPal records'}</span>
                <time>{timeAgo(run.created_at)}</time>
              </span>
              {run.result && appCaptures != null && (
                <span className="mobile-run-proof">PayPal {run.result.observed.captures} · app {appCaptures} captures</span>
              )}
            </button>
          )
        })}
      </section>
    </div>
  )
}
