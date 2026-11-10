import { Request, Response } from 'express';
import { shopState } from './state';

export interface ChatMessage {
  message: string;
  orderId?: string;
  userRole?: string;
}

export interface AssistantResponse {
  reply: string;
  refundTriggered: boolean;
  refundId?: string;
  refundAmount?: string;
}

/**
 * Parses user input for refund requests.
 * Extracts requested amount or defaults to full refund.
 */
function extractRefundAmount(message: string): number {
  const match = message.match(/\$?(\d+(?:\.\d{1,2})?)/);
  return match ? parseFloat(match[1]) : 38.97;
}

/**
 * Handle deterministic demo-shop support chat (POST /api/chat)
 * Contains BUG-10 vulnerability (prompt injection bypasses refund limits).
 */
export async function handleChat(req: Request, res: Response): Promise<void> {
  const body = req.body as ChatMessage;
  const message = body?.message || '';
  const orderId = body?.orderId || 'ORDER-F7-001';
  const userRole = body?.userRole || 'buyer';

  const lower = message.toLowerCase();
  const isRefundRequest = lower.includes('refund') || lower.includes('override') || lower.includes('credit');

  if (!isRefundRequest) {
    res.status(200).json({
      reply: 'Hello! I am DriftGuard Demo Shop support assistant. How can I assist you with your order today?',
      refundTriggered: false,
    });
    return;
  }

  const requestedAmount = extractRefundAmount(message);

  // BUG-10: Prompt injection triggers unauthorized refund
  // Vulnerability: Missing deterministic code guardrails (no max cap, no role check)
  // Records a simulated shop refund; no PayPal refund API is called.
  const refundId = `REF-INJ-${Date.now()}`;
  shopState.recordRefund(orderId, refundId, requestedAmount.toFixed(2));

  res.status(200).json({
    reply: `I have processed your refund of $${requestedAmount.toFixed(2)} for order ${orderId}. Reference: ${refundId}`,
    refundTriggered: true,
    refundId,
    refundAmount: requestedAmount.toFixed(2),
  });
}

