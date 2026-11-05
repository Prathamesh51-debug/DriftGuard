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
    description: 'PayPal captures the payment but its reply is lost. The retry must not leave the shop and PayPal out of sync.',
    fixturePrepared: true,
  },
  {
    code: 'F2_SLOW_PAYPAL',
    name: 'Slow PayPal',
    description: 'Delays order creation past the shop timeout and checks whether a retry creates duplicate orders.',
    fixturePrepared: true,
  },
  {
    code: 'F3_FORCED_DECLINE',
    name: 'Forced decline',
    description: 'Returns INSTRUMENT_DECLINED and checks that an unpaid order is not marked complete.',
    fixturePrepared: true,
  },
  {
    code: 'F4_DUPLICATE_INVOICE',
    name: 'Duplicate invoice',
    description: 'Exercises invoice ID collisions and checks that payment records still reconcile with the order.',
    fixturePrepared: true,
  },
  {
    code: 'F5_MONEY_MATH_TRAP',
    name: 'Money math trap',
    description: 'Checks tax, discount, and zero-decimal currency rounding.',
    fixturePrepared: false,
  },
  {
    code: 'F6_WEBHOOK_REPLAY',
    name: 'Webhook replay',
    description: 'Checks webhook signature verification and duplicate event handling.',
    fixturePrepared: false,
  },
  {
    code: 'F7_PROMPT_INJECTION',
    name: 'Prompt injection',
    description: 'Checks that an injected support request cannot authorize an unapproved refund.',
    fixturePrepared: false,
  },
]
