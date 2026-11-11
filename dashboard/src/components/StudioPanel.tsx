import { AgStudio, AgStudioProvider } from 'ag-studio-react'
import { AgStudioAiModule, AgStudioModuleRegistry, studioTheme } from 'ag-studio'
import type { AgStudioApi, AgStudioProperties } from 'ag-studio'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AI_URL } from '../api'
import type { Run } from '../types'
import { RUN_FIELDS, toRunRows } from '../studioData'
import { initialReport } from '../studioReport'
import { createAnthropicAdapter } from '../studioAgent/anthropicAdapter'
import { buildHarness } from '../studioAgent/harness'

// The AI Assistant panel is an optional module: without this the panel is silently absent.
AgStudioModuleRegistry.registerModules([AgStudioAiModule])

const SHARED_THEME_PARAMS = {
  fontFamily: 'Inter, system-ui, sans-serif',
  studioAiPanelWidth: 420,
}

const DARK_STUDIO_THEME = studioTheme.withParams({
  ...SHARED_THEME_PARAMS,
  backgroundColor: '#12161c',
  foregroundColor: '#e6e9ee',
  textColor: '#e6e9ee',
  subtleTextColor: '#9aa4b2',
  inputBackgroundColor: '#171c24',
  inputTextColor: '#e6e9ee',
  inputPlaceholderTextColor: '#9aa4b2',
  borderColor: '#262d38',
  accentColor: '#5b9dff',
  menuBackgroundColor: '#171c24',
  menuTextColor: '#e6e9ee',
  studioCanvasBackgroundColor: '#0e1116',
  studioWidgetBackgroundColor: '#171c24',
  studioWidgetBorder: { width: 1, color: '#262d38' },
  studioAiPanelInputMessageBackgroundColor: '#1b2940',
})

const LIGHT_STUDIO_THEME = studioTheme.withParams({
  ...SHARED_THEME_PARAMS,
  backgroundColor: '#ffffff',
  foregroundColor: '#1a2433',
  textColor: '#1a2433',
  subtleTextColor: '#5f6c7d',
  inputBackgroundColor: '#ffffff',
  inputTextColor: '#1a2433',
  inputPlaceholderTextColor: '#5f6c7d',
  borderColor: '#e3e8ef',
  accentColor: '#2f5bea',
  menuBackgroundColor: '#f3f6fa',
  menuTextColor: '#1a2433',
  studioCanvasBackgroundColor: '#f3f6fa',
  studioWidgetBackgroundColor: '#ffffff',
  studioWidgetBorder: { width: 1, color: '#e3e8ef' },
  studioAiPanelInputMessageBackgroundColor: '#e5ecfd',
})

const LICENCE_KEY: string | undefined = import.meta.env.VITE_AG_STUDIO_KEY
const adapter = createAnthropicAdapter(AI_URL)
// Hoist static AgStudio props so unrelated React re-renders never trigger AG Studio's
// reference-equality checks to rebuild side panels or clear AI input focus.
const STUDIO_STYLE = { flex: 1, minHeight: 0 }
const STUDIO_PANELS: AgStudioProperties['panels'] = { edit: { right: ['ai', 'edit', 'data'] } }
const STUDIO_LOCALE_TEXT = { panelTitleAi: 'Ask Studio' }
const STUDIO_FIELDS = RUN_FIELDS.map((f) => ({ ...f }))

export default function StudioPanel({ runs, sampleMode, theme }: { runs: Run[]; sampleMode: boolean; theme: 'light' | 'dark' }) {
  const runsRef = useRef(runs)
  const [modelStatus, setModelStatus] = useState<'checking' | 'configured' | 'preview' | 'offline'>('checking')
  useEffect(() => {
    runsRef.current = runs
  }, [runs])
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${AI_URL}/health`, { signal: controller.signal })
      .then(async (response) => response.ok ? response.json() as Promise<{ model_ready?: boolean }> : Promise.reject())
      .then((health) => setModelStatus(health.model_ready ? 'configured' : 'preview'))
      .catch(() => { if (!controller.signal.aborted) setModelStatus('offline') })
    return () => controller.abort()
  }, [])
  const ai = useMemo(() => ({ api }: { api: AgStudioApi }) => buildHarness(api, adapter, () => runsRef.current), [])
  const data = useMemo(() => ({ sources: [{ id: 'runs', name: 'Runs', description: 'One row per DriftGuard chaos run.', data: toRunRows(runs), fields: STUDIO_FIELDS }] }), [runs])
  const activeTheme = theme === 'light' ? LIGHT_STUDIO_THEME : DARK_STUDIO_THEME

  return (
    <div className="studio-wrap" data-ag-theme-mode={theme}>
      <p className="s02-note">
        {sampleMode && 'Studio is exploring sample run data. '}
        {modelStatus === 'configured' ? 'Claude is configured on the server.' : modelStatus === 'preview' ? 'AI preview answers are labeled; no Claude call is made.' : modelStatus === 'offline' ? 'The AI service is unreachable.' : 'Checking AI service…'}
      </p>
      <AgStudioProvider licenseKey={LICENCE_KEY}>
        <AgStudio
          style={STUDIO_STYLE}
          theme={activeTheme}
          data={data}
          initialState={initialReport}
          mode="edit"
          panels={STUDIO_PANELS}
          localeText={STUDIO_LOCALE_TEXT}
          ai={ai}
        />
      </AgStudioProvider>
    </div>
  )
}
