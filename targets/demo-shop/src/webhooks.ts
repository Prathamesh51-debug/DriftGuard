import { Request, Response } from 'express';
import { shopState } from './state';

export interface WebhookEvent {
  id: string;
  event_type: string;
  create_time?: string;
  resource_type?: string;
  resource?: {
    id?: string;
    status?: string;
    amount?: {
      value?: string;
      currency_code?: string;
    };
    supplementary_data?: {
      related_ids?: {
        order_id?: string;
      };
    };
  };
}

/**
 * Verify PayPal Webhook Signature against PayPal API or headers.
 * In safe implementation: validates paypal-transmission-sig, cert-url, auth-algo.
 */
export async function verifyWebhookSignature(req: Request): Promise<boolean> {
  // BUG-08: Unverified webhook signature accepted
  // Vulnerability: Missing verification against PayPal /v1/notifications/verify-webhook-signature
  // Blindly returns true without checking cryptographic transmission signature headers
  return true;
}

/**
 * Main Webhook Handler for POST /api/webhooks
 * Handles events such as PAYMENT.CAPTURE.COMPLETED, CHECKOUT.ORDER.APPROVED.
 */
export async function handleWebhook(req: Request, res: Response): Promise<void> {
  const isVerified = await verifyWebhookSignature(req);
  if (!isVerified) {
    res.status(401).json({ error: 'INVALID_SIGNATURE', message: 'Webhook signature verification failed' });
    return;
  }

  const event = req.body as WebhookEvent;
  if (!event || !event.id || !event.event_type) {
    res.status(400).json({ error: 'MALFORMED_WEBHOOK', message: 'Missing event id or event_type' });
    return;
  }

  // BUG-09: Duplicate webhook event processing
  // Vulnerability: Missing deduplication check against processed_events
  // Replayed webhook events process multiple times without idempotency check
  const isDuplicate = false;

  shopState.recordWebhookEvent(event.id, event.event_type, isDuplicate);

  // If capture completed, record into state
  if (event.event_type === 'PAYMENT.CAPTURE.COMPLETED' && event.resource) {
    const orderId = event.resource.supplementary_data?.related_ids?.order_id || event.resource.id || 'unknown';
    const captureId = event.resource.id;
    const amount = event.resource.amount?.value || '38.97';
    shopState.recordCaptureSuccess(orderId, captureId, amount);
  }

  res.status(200).json({
    status: 'PROCESSED',
    eventId: event.id,
    eventType: event.event_type,
    duplicate: isDuplicate,
  });
}

