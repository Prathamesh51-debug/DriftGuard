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

/**
 * Creates a PayPal v2 Checkout Order for $38.97 USD.
 * SEEDED BUGS:
 * - BUG-02: Blind retry loop on createOrder timeout without paypalRequestId.
 * - BUG-04: Random non-deterministic invoice ID.
 */
export async function createCheckoutOrder(amount: string = '38.97'): Promise<CreateOrderResult> {
  const returnUrl = process.env.PAYPAL_RETURN_URL || 'http://localhost:3000/return';
  const cancelUrl = process.env.PAYPAL_CANCEL_URL || 'http://localhost:3000/cancel';

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
                currencyCode: 'USD',
                value: amount,
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
      shopState.recordOrder(orderId, amount);

      const links = result.links || [];
      const approveLink = links.find((l: any) => l.rel === 'payer-action' || l.rel === 'approve');
      const approveUrl = approveLink?.href || '';

      return {
        orderId,
        approveUrl,
        amount,
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

      shopState.recordCaptureSuccess(orderId, captureId, '38.97');

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
      if (statusCode === 422) {
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
