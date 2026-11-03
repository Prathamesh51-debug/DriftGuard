import { faultLabel, shortId } from '../format'
import type { Run } from '../types'

/**
 * Plain-text facts about stored runs, written by code from the stored Result. The Studio agent
 * explains a run only from this text, so every number and ID it quotes exists in the record.
 */

export function findRun(runs: Run[], idOrSuffix: string): Run | undefined {
  const wanted = idOrSuffix.trim().toLowerCase()
  if (!wanted) return undefined
  return runs.find((r) => r.run_id.toLowerCase() === wanted) ?? runs.find((r) => r.run_id.toLowerCase().endsWith(wanted))
}

export function describeRun(run: Run): string {
  const { scenario, result } = run
  const lines = [
    `Run ${run.run_id} (short id ${shortId(run.run_id)})`,
    `Fault injected: ${faultLabel(scenario.fault)}${scenario.description ? ` - ${scenario.description}` : ''}`,
    `Where in the app: ${scenario.target_call.file}:${scenario.target_call.line}${scenario.target_call.method ? ` (${scenario.target_call.method})` : ''}`,
    `What was done to the call: ${scenario.inject.action} on ${scenario.inject.on}`,
    `What a correct app does: ${scenario.expect.captures_per_purchase} capture per purchase${scenario.expect.amount ? `, ${scenario.expect.amount} ${scenario.expect.currency}` : ''}`,
  ]
  if (run.rerun_of) lines.push(`This run repeats run ${run.rerun_of}`)
  if (!result) {
    lines.push(`Status: ${run.status}. No result yet, so there is nothing to explain.`)
    return lines.join('\n')
  }
  const { observed, evidence } = result
  lines.push(
    `Verdict: ${result.verdict}`,
    `Rule checked: ${result.rule}`,
    `PayPal's own records show ${observed.captures} capture(s), ${observed.amount_captured} captured`,
  )
  if (observed.app_recorded_captures != null) lines.push(`The app itself recorded ${observed.app_recorded_captures} capture(s)`)
  if (observed.refunds_issued != null) lines.push(`Refunds issued: ${observed.refunds_issued}`)
  lines.push(`Money impact: ${result.money_impact}`)
  if (result.error_message) lines.push(`Error: ${result.error_message}`)
  if (evidence.paypal_order_ids.length) lines.push(`PayPal order IDs: ${evidence.paypal_order_ids.join(', ')}`)
  if (evidence.paypal_capture_ids.length) lines.push(`PayPal capture IDs: ${evidence.paypal_capture_ids.join(', ')}`)
  return lines.join('\n')
}

export function listRuns(runs: Run[]): string {
  if (runs.length === 0) return 'There are no runs yet.'
  return runs
    .map((r) => `${shortId(r.run_id)}  ${faultLabel(r.scenario.fault)}  ${r.status === 'complete' ? (r.result?.verdict ?? 'NO RESULT') : 'RUNNING'}  ${r.result?.money_impact ?? ''}`.trimEnd())
    .join('\n')
}

export const AGENT_ADDENDUM = [
  'You are also DriftGuard\'s run investigator. DriftGuard injects a fault into a payment flow and checks PayPal\'s own records afterwards.',
  'When asked why a run failed, what it means or what it cost, call explain_run (or list_runs to find the run) and answer ONLY from what the tool returns.',
  'Quote only numbers, amounts and IDs that appear in the tool output. If something is not in the output, say it is not in the record. Never guess a cause that the record does not show.',
  'Be short and plain: say what the buyer paid, what the app recorded, and what that means.',
].join(' ')
