import { AgStudio, AgStudioProvider } from 'ag-studio-react'
import { AgStudioAiModule, AgStudioModuleRegistry, studioTheme } from 'ag-studio'
import type { AgStudioApi } from 'ag-studio'
import { useEffect, useMemo, useRef } from 'react'
import { AI_URL } from '../api'
import type { Run } from '../types'
import { RUN_FIELDS, toRunRows } from '../studioData'
import { initialReport } from '../studioReport'
import { createAnthropicAdapter } from '../studioAgent/anthropicAdapter'
import { buildHarness } from '../studioAgent/harness'

// The AI Assistant panel is an optional module: without this the panel is silently absent.
AgStudioModuleRegistry.registerModules([AgStudioAiModule])

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
  studioAiPanelWidth: 420,
  studioAiPanelInputMessageBackgroundColor: '#1b2940',
})

const LICENCE_KEY: string | undefined = import.meta.env.VITE_AG_STUDIO_KEY
const adapter = createAnthropicAdapter(AI_URL)

export default function StudioPanel({ runs }: { runs: Run[] }) {
  const runsRef = useRef(runs)
  useEffect(() => {
    runsRef.current = runs
  }, [runs])
  const ai = useMemo(() => ({ api }: { api: AgStudioApi }) => buildHarness(api, adapter, () => runsRef.current), [])
  const data = useMemo(() => ({ sources: [{ id: 'runs', name: 'Runs', description: 'One row per DriftGuard chaos run.', data: toRunRows(runs), fields: RUN_FIELDS.map((f) => ({ ...f })) }] }), [runs])

  return (
    <div className="studio-wrap">
      <AgStudioProvider licenseKey={LICENCE_KEY}>
        <AgStudio
          style={{ height: '100%' }}
          theme={theme}
          data={data}
          initialState={initialReport}
          mode="edit"
          panels={{ edit: { right: ['ai', 'edit', 'data'] } }}
          localeText={{ panelTitleAi: 'Ask Studio' }}
          ai={ai}
        />
      </AgStudioProvider>
    </div>
  )
}
