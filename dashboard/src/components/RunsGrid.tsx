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

export function RunsGrid({
  runs,
  selectedId,
  onSelect,
  loading,
  emptyMessage,
}: {
  runs: Run[]
  selectedId: string | null
  onSelect: (runId: string) => void
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
      <AgGridReact<Run>
        ref={gridRef}
        theme={theme}
        rowData={runs}
        columnDefs={columns}
        getRowId={(p) => p.data.run_id}
        onRowClicked={(e) => e.data && onSelect(e.data.run_id)}
        getRowClass={(p) => (p.data?.run_id === selectedId ? 'row-selected' : '')}
        loading={loading}
        noRowsOverlayComponent={EmptyOverlay}
        noRowsOverlayComponentParams={{ message: emptyMessage }}
        suppressCellFocus
      />
    </div>
  )
}
