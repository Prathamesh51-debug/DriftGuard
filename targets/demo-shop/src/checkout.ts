/**
 * DriftGuard Demo Shop - Checkout Controller
 * Implements PayPal Orders v2 integration for order creation and capture.
 *
 * SEEDED VULNERABILITY:
 * - BUG-01 (F1 Lost Capture): Capture timeout blind retry without idempotency key.
 *   When mitmproxy drops the HTTP 201 response and injects a 504 Gateway Timeout,
 *   this controller catches the error and blindly retries captureOrder without
 *   sending a deterministic PayPal-Request-Id header, causing duplicate charges.
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
 */
export async function createCheckoutOrder(amount: string = '38.97'): Promise<CreateOrderResult> {
  const returnUrl = process.env.PAYPAL_RETURN_URL || 'http://localhost:3000/return';
  const cancelUrl = process.env.PAYPAL_CANCEL_URL || 'http://localhost:3000/cancel';
  const { result } = await ordersController.createOrder({
    body: {
      intent: CheckoutPaymentIntent.Capture,
      purchaseUnits: [
        {
          referenceId: `cart-${Date.now()}`,
          description: 'Autonomous Agent Guardrails Subscription',
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
}

/**
 * Captures payment for an approved order.
 * BUG-01: Contains blind retry loop without PayPal-Request-Id on network drops.
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
