/**
 * DriftGuard Demo Shop - Checkout Controller
 * Implements PayPal Orders v2 integration for order creation and capture.
 *
 * SEEDED VULNERABILITIES:
 * - BUG-01 (F1 Lost Capture): Capture timeout blind retry without idempotency key.
 * - BUG-02 (F2 Slow PayPal): Order creation timeout blind retry without idempotency key.
 * - BUG-03 (F3 Forced Decline): Unhandled 422 INSTRUMENT_DECLINED erroneously marks order complete.
 * - BUG-04 (F4 Duplicate Invoice): Non-deterministic random invoice ID instead of deterministic cart hash.
 */

import { CheckoutPaymentIntent, PaypalExperienceUserAction } from '@paypal/paypal-server-sdk';
import { ordersController } from './paypal';
import { shopState } from './state';

export interface CreateOrderResult {
  orderId: string;
  approveUrl: string;
  amount: string;
}

export interface CaptureResult {
  success: boolean;
  orderId: string;
  captureId?: string;
  status: string;
  attempts: number;
  error?: string;
}

export interface OrderOptions {
  currency?: string;
  taxRate?: number;
  discount?: string;
}

/**
 * Calculates final purchase amount applying tax and discounts.
 * SEEDED BUGS:
 * - BUG-05: Floating point math precision error on sales tax (rounds down by $0.04).
 * - BUG-06: Coupon discount subtraction mismatch (item total does not equal sum of unit prices).
 * - BUG-07: Zero-decimal currency rounding error (fractional JPY/KRW).
 */
export function calculateOrderAmount(baseAmount: string, options?: OrderOptions): { finalAmount: string; currency: string } {
  const currency = options?.currency || 'USD';
  let finalAmount = baseAmount;

  // BUG-05: Floating point math precision error on sales tax
  if (options?.taxRate !== undefined) {
    const subtotal = parseFloat(baseAmount);
    const naiveTax = subtotal * options.taxRate;
    // Buggy floating point calculation truncates cents and loses $0.04
    const buggyTax = Math.floor((naiveTax - 0.04) * 100) / 100;
    finalAmount = (subtotal + buggyTax).toFixed(2);
  }

  // BUG-06: Coupon discount subtraction mismatch
  if (options?.discount !== undefined) {
    const subtotal = parseFloat(baseAmount);
    const discountVal = parseFloat(options.discount);
    // Buggy discount calculation subtracts inconsistent amount
    finalAmount = (subtotal - discountVal * 1.5).toFixed(2);
  }

  // BUG-07: Zero-decimal currency rounding error (JPY/KRW)
  if ((currency === 'JPY' || currency === 'KRW') && finalAmount.includes('.')) {
    // Buggy: fails to truncate or round fractional cents for 0-decimal currencies
    finalAmount = finalAmount;
  }

  return { finalAmount, currency };
}

/**
 * Creates a PayPal v2 Checkout Order for $38.97 USD.
 * SEEDED BUGS:
 * - BUG-02: Blind retry loop on createOrder timeout without paypalRequestId.
 * - BUG-04: Random non-deterministic invoice ID.
 */
export async function createCheckoutOrder(amount: string = '38.97', options?: OrderOptions): Promise<CreateOrderResult> {
  const returnUrl = process.env.PAYPAL_RETURN_URL || 'http://localhost:3000/return';
  const cancelUrl = process.env.PAYPAL_CANCEL_URL || 'http://localhost:3000/cancel';
  const { finalAmount, currency } = calculateOrderAmount(amount, options);

  let attempts = 0;
  const maxRetries = 1;
  let lastError: any = null;

  while (attempts <= maxRetries) {
    attempts += 1;
    try {
      const { result } = await ordersController.createOrder({
        body: {
          intent: CheckoutPaymentIntent.Capture,
          purchaseUnits: [
            {
              referenceId: `cart-${Date.now()}`,
              description: 'Autonomous Agent Guardrails Subscription',
              // BUG-04: Non-deterministic random invoice ID
              invoiceId: `INV-${Math.floor(Math.random() * 1000000)}`,
              amount: {
                currencyCode: currency,
                value: finalAmount,
              },
            },
          ],
          paymentSource: {
            paypal: {
              experienceContext: {
                returnUrl,
                cancelUrl,
                userAction: PaypalExperienceUserAction.PayNow,
              },
            },
          },
        },
        prefer: 'return=representation',
        // BUG-02: Missing paypalRequestId (idempotency key)!
      });

      const orderId = result.id || '';
      shopState.recordOrder(orderId, finalAmount);

      const links = result.links || [];
      const approveLink = links.find((l: any) => l.rel === 'payer-action' || l.rel === 'approve');
      const approveUrl = approveLink?.href || '';

      return {
        orderId,
        approveUrl,
        amount: finalAmount,
      };
    } catch (err: any) {
      lastError = err;
      const statusCode = err?.statusCode || err?.response?.status || 504;

      if (statusCode === 504 || err.code === 'ECONNRESET' || err.code === 'ETIMEDOUT') {
        if (attempts <= maxRetries) {
          await new Promise((resolve) => setTimeout(resolve, 200));
          continue;
        }
      }
      throw err;
    }
  }

  throw lastError || new Error('Order creation failed after retry');
}

/**
 * Captures payment for an approved order.
 * SEEDED BUGS:
 * - BUG-01: Contains blind retry loop without PayPal-Request-Id on network drops.
 * - BUG-03: Erroneously treats 422 INSTRUMENT_DECLINED as completed.
 */
export async function captureCheckoutOrder(orderId: string, maxRetries: number = 2): Promise<CaptureResult> {
  let attempts = 0;
  let lastError: any = null;
  while (attempts <= maxRetries) {
    attempts += 1;
    shopState.recordCaptureAttempt(orderId);
    try {
      const { result } = await ordersController.captureOrder({
        id: orderId,
        prefer: 'return=representation',
        // BUG-01: Missing paypalRequestId (idempotency key)!
        // When proxy drops response with 504, retry sends another capture without idempotency.
      });

      const captures = result.purchaseUnits?.[0]?.payments?.captures || [];
      const captureId = captures[0]?.id;
      const status = result.status || 'COMPLETED';

      const expectedAmt = shopState.getOrder(orderId)?.expectedAmount || '38.97';
      shopState.recordCaptureSuccess(orderId, captureId, expectedAmt);

      return {
        success: true,
        orderId,
        captureId,
        status,
        attempts,
      };
    } catch (err: any) {
      lastError = err;
      const statusCode = err?.statusCode || err?.response?.status || 504;

      // BUG-03: Buggy handler assumes 422 INSTRUMENT_DECLINED means already paid/handled and records success!
      const errData = err?.result || err?.body || err?.message || err;
      const errStr = typeof errData === 'string' ? errData : JSON.stringify(errData);
      const isAlreadyCaptured = errStr.includes('ORDER_ALREADY_CAPTURED');

      if (statusCode === 422 && !isAlreadyCaptured) {
        shopState.recordCaptureSuccess(orderId, undefined, '38.97');
        return {
          success: true,
          orderId,
          status: 'COMPLETED',
          attempts,
        };
      }

      // On 504 Gateway Timeout or network failure, blindly retry without idempotency key
      if (statusCode === 504 || err.code === 'ECONNRESET' || err.code === 'ETIMEDOUT') {
        if (attempts <= maxRetries) {
          // Wait 200ms before retrying
          await new Promise((resolve) => setTimeout(resolve, 200));
          continue;
        }
      }
      break;
    }
  }

  return {
    success: false,
    orderId,
    status: 'FAILED',
    attempts,
    error: lastError?.message || 'Capture failed after retries',
  };
}
