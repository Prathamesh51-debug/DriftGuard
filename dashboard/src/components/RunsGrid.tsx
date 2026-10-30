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

export function RunsGrid({
  runs,
  selectedId,
  onSelect,
}: {
  runs: Run[]
  selectedId: string | null
  onSelect: (runId: string) => void
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
        headerName: 'Captures',
        width: 120,
        type: 'rightAligned',
        cellRenderer: (p: ICellRendererParams<Run>) => {
          const r = p.data?.result
          if (!p.data || !r) return <span className="muted">—</span>
          const want = p.data.scenario.expect.captures_per_purchase
          const bad = r.observed.captures !== want
          return (
            <span className={`mono ${bad ? 'bad' : ''}`}>
              {r.observed.captures} / {want}
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
        noRowsOverlayComponent={() => <span className="muted">No runs yet. Launch one.</span>}
        suppressCellFocus
      />
    </div>
  )
}
