import type { Run } from './types'
import { faultLabel, shortId } from './format'

/** One flat row per run: the shape AG Studio needs for its tables, charts and the agent's queries. */
export interface RunRow {
  run_id: string
  source: string
  fault: string
  verdict: string
  rule: string
  paypal_captures: number | null
  app_recorded_captures: number | null
  /** PayPal's count minus the app's own count: non-zero means the app lost track of a payment. */
  capture_drift: number | null
  amount_captured: number | null
  amount_expected: number | null
  money_impact: string
  started: string
  rerun_of: string | null
}

const num = (v: string | null | undefined): number | null => (v == null || v === '' || Number.isNaN(Number(v)) ? null : Number(v))

export function toRunRows(runs: Run[]): RunRow[] {
  return runs.map((run) => {
    const r = run.result
    const app = r?.observed.app_recorded_captures ?? null
    return {
      run_id: shortId(run.run_id),
      source: run.mode === 'sample' ? 'Sample fixture' : 'Live engine',
      fault: faultLabel(run.scenario.fault),
      verdict: r?.verdict ?? 'RUNNING',
      rule: r?.rule ?? '',
      paypal_captures: r?.observed.captures ?? null,
      app_recorded_captures: app,
      capture_drift: r && app !== null ? r.observed.captures - app : null,
      amount_captured: num(r?.observed.amount_captured),
      amount_expected: num(run.scenario.expect.amount),
      money_impact: r?.money_impact ?? '',
      started: new Date(run.created_at * 1000).toISOString(),
      rerun_of: run.rerun_of ? shortId(run.rerun_of) : null,
    }
  })
}

/** Explicit fields so the dashboard and the agent get readable names and know what each column means. */
export const RUN_FIELDS = [
  { id: 'run_id', name: 'Run', format: 'textFormat', description: "Short id of the chaos run." },
  { id: 'source', name: 'Source', format: 'textFormat', description: "Sample fixture or live engine; sample data is not a new Sandbox transaction." },
  { id: 'fault', name: 'Fault', format: 'textFormat', description: "The injected failure, for example F1 Lost capture response." },
  { id: 'verdict', name: 'Verdict', format: 'textFormat', description: "PASS, FAIL, ERROR, or RUNNING. FAIL means PayPal's records broke a safety rule." },
  { id: 'rule', name: 'Rule', format: 'textFormat', description: "The safety rule the run was checked against." },
  { id: 'paypal_captures', name: 'Captures in PayPal', format: 'integerFormat', description: "PayPal capture count in a live run, or the prepared PayPal count in a sample fixture. Check Source." },
  { id: 'app_recorded_captures', name: 'Captures in the app', format: 'integerFormat', description: "How many captures the shop app recorded itself." },
  { id: 'capture_drift', name: 'Capture drift', format: 'integerFormat', description: "PayPal captures minus app captures. Above zero means the buyer paid but the app lost the order." },
  { id: 'amount_captured', name: 'Amount captured', format: 'decimalFormat', description: "Total captured in PayPal, in the test currency." },
  { id: 'amount_expected', name: 'Amount expected', format: 'decimalFormat', description: "What the test expected to be captured." },
  { id: 'money_impact', name: 'Money impact', format: 'textFormat', description: "Plain-English financial summary written by the reconciler." },
  { id: 'started', name: 'Started', format: 'dateTimeFormat', description: "When the run started (ISO time)." },
  { id: 'rerun_of', name: 'Re-run of', format: 'textFormat', description: "The run this one repeats after a fix, if any." },
] as const
