// Mirrors contracts/models.py. The run envelope (run_id, status, created_at)
// is served by the mock runner until the real engine API defines it.

export type Verdict = 'PASS' | 'FAIL' | 'ERROR'

export interface TargetCall {
  file: string
  line: number
  method: string | null
}

export interface InjectAction {
  on: string
  action: string
  mock_header: string | null
  delay_ms: number | null
  payload: Record<string, unknown> | null
}

export interface Expectation {
  captures_per_purchase: number
  amount: string | null
  currency: string
  no_refund_issued: boolean | null
}

export interface Scenario {
  scenario_id: string
  fault: string
  description: string | null
  target_call: TargetCall
  inject: InjectAction
  expect: Expectation
}

export interface ObservedState {
  captures: number
  amount_captured: string
  orders_created: number | null
  refunds_issued: number | null
  app_recorded_captures?: number | null
}

export interface Evidence {
  paypal_order_ids: string[]
  paypal_capture_ids: string[]
  paypal_refund_ids: string[]
  proxy_log_refs: string[]
  webhook_event_ids: string[]
}

export interface Result {
  scenario_id: string
  verdict: Verdict
  rule: string
  observed: ObservedState
  evidence: Evidence
  money_impact: string
  error_message: string | null
}

export interface Run {
  run_id: string
  status: 'running' | 'complete'
  created_at: number
  scenario: Scenario
  result: Result | null
  rerun_of: string | null
}
