import type { AgReportState } from 'ag-studio'

/** Field ids in widget configs are `<source id>.<field id>`. */
const f = (field: string) => `runs.${field}`
const title = (text: string) => ({
  title: { text, enabled: true, typography: { fontSize: 13, fontWeight: 'bold' as const } },
})
const bigNumber = (text: string, color?: string) => ({
  ...title(text),
  style: { typography: { fontSize: 36, fontWeight: 'bold' as const }, color, textAlign: 'left' as const, verticalAlign: 'center' as const },
})

/** The starting dashboard: headline numbers, verdicts by fault, and the runs table. Users (and the agent) can change it. */
export const initialReport: AgReportState = {
  selectedPageId: 'overview',
  pages: [
    {
      id: 'overview',
      layout: {
        columns: 12,
        rowHeight: 56,
        pagePadding: 12,
        widgetBorderRadius: 8,
      },
      widgets: {
        runs: { type: 'value', format: bigNumber('Runs'), dataMapping: { value: [{ id: f('run_id'), aggregation: 'count' }] } },
        paypal: {
          type: 'value',
          format: bigNumber('Captures in PayPal'),
          dataMapping: { value: [{ id: f('paypal_captures'), aggregation: 'sum' }] },
        },
        drift: {
          type: 'value',
          format: bigNumber('Captures the app lost', '#ff6b6b'),
          dataMapping: { value: [{ id: f('capture_drift'), aggregation: 'sum' }] },
        },
        byVerdict: {
          type: 'column-chart-grouped',
          format: title('Runs by verdict'),
          dataMapping: { categoryKey: [{ id: f('verdict') }], valueKey: [{ id: f('run_id'), aggregation: 'count' }] },
        },
        table: {
          type: 'grid',
          format: title('Runs'),
          dataMapping: {
            cols: [
              { id: f('run_id') }, { id: f('fault') }, { id: f('verdict') }, { id: f('paypal_captures') },
              { id: f('app_recorded_captures') }, { id: f('money_impact') },
            ],
          },
        },
      },
      widgetLayout: {
        runs: { xTrack: 0, yTrack: 0, xSpan: 3, ySpan: 2 },
        paypal: { xTrack: 3, yTrack: 0, xSpan: 3, ySpan: 2 },
        drift: { xTrack: 6, yTrack: 0, xSpan: 3, ySpan: 2 },
        byVerdict: { xTrack: 9, yTrack: 0, xSpan: 3, ySpan: 4 },
        table: { xTrack: 0, yTrack: 2, xSpan: 9, ySpan: 5 },
      },
    },
  ],
}
