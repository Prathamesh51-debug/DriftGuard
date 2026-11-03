import { AgStudio, AgStudioProvider } from 'ag-studio-react'
import { studioTheme } from 'ag-studio'
import { useMemo } from 'react'
import type { Run } from '../types'
import { RUN_FIELDS, toRunRows } from '../studioData'
import { initialReport } from '../studioReport'

const theme = studioTheme.withParams({
  backgroundColor: '#12161c',
  foregroundColor: '#e6e9ee',
  textColor: '#e6e9ee',
  subtleTextColor: '#9aa4b2',
  borderColor: '#262d38',
  accentColor: '#5b9dff',
  menuBackgroundColor: '#171c24',
  menuTextColor: '#e6e9ee',
  fontFamily: 'Inter, system-ui, sans-serif',
})

const LICENCE_KEY: string | undefined = import.meta.env.VITE_AG_STUDIO_KEY

export default function StudioPanel({ runs }: { runs: Run[] }) {
  const data = useMemo(() => ({ sources: [{ id: 'runs', name: 'Runs', description: 'One row per DriftGuard chaos run.', data: toRunRows(runs), fields: RUN_FIELDS.map((f) => ({ ...f })) }] }), [runs])

  return (
    <div className="studio-wrap">
      <AgStudioProvider licenseKey={LICENCE_KEY}>
        <AgStudio style={{ height: '100%' }} theme={theme} data={data} initialState={initialReport} mode="edit" />
      </AgStudioProvider>
    </div>
  )
}
