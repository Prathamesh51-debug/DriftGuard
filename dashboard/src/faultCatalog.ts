export interface FaultDefinition {
  code: string
  name: string
  description: string
  fixturePrepared: boolean
}

/** Mirrors FaultType in contracts/models.py and the current scenario fixtures. */
export const FAULT_CATALOG: FaultDefinition[] = [
  {
    code: 'F1_LOST_CAPTURE_RESPONSE',
    name: 'Lost capture response',
    description:
      'PayPal captures the payment (HTTP 201), then mitmproxy drops the reply and returns HTTP 504. Checks whether the shop reconciles order status instead of failing a blind retry and leaving a paid order unfulfilled.',
    fixturePrepared: true,
  },
  {
    code: 'F2_SLOW_PAYPAL',
    name: 'Slow PayPal',
    description:
      'Delays the first create-order response by 1s and returns HTTP 504 at the proxy. Checks whether the shop sends a stable PayPal-Request-Id instead of creating duplicate Sandbox orders on retry.',
    fixturePrepared: true,
  },
  {
    code: 'F3_FORCED_DECLINE',
    name: 'Forced decline',
    description:
      'Forces HTTP 422 INSTRUMENT_DECLINED on capture via PayPal-Mock-Response or proxy override. Checks that the shop surfaces the decline and records 0 captures when PayPal collected $0.00.',
    fixturePrepared: true,
  },
  {
    code: 'F4_DUPLICATE_INVOICE',
    name: 'Duplicate invoice',
    description:
      'Enforces deterministic cart-hashed invoice IDs at the proxy: colliding or unstable IDs receive a simulated HTTP 409 DUPLICATE_INVOICE_ID on capture, checking retry identity and single-capture reconciliation.',
    fixturePrepared: true,
  },
  {
    code: 'F5_MONEY_MATH_TRAP',
    name: 'Money math trap',
    description:
      'Exercises floating-point tax math in the demo shop that undercharges by $0.04 ($38.92 captured vs $38.96 expected). Reconciles PayPal captured funds against exact expected decimal amounts.',
    fixturePrepared: true,
  },
  {
    code: 'F6_WEBHOOK_REPLAY',
    name: 'Webhook replay',
    description:
      'Delivers the same PAYMENT.CAPTURE.COMPLETED webhook event twice to the shop endpoint. Verifies idempotent deduplication so the shop processes the event once while PayPal holds a single capture.',
    fixturePrepared: true,
  },
  {
    code: 'F7_PROMPT_INJECTION',
    name: 'Prompt injection',
    description:
      'Injects an adversarial buyer chat prompt requesting a full refund above policy limits. Verifies deterministic code guardrails block over-limit non-admin requests before recording any simulated refund.',
    fixturePrepared: true,
  },
]
