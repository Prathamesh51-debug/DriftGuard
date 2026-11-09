/**
 * DriftGuard Demo Shop - Internal Application Ledger State
 * Exposes internal memory state via GET /_driftguard/state for the Reconciler
 * to mathematically prove drift between target local state and PayPal's ground truth.
 */

export interface DemoOrder {
  orderId: string;
  status: 'CREATED' | 'SAVED' | 'APPROVED' | 'VOIDED' | 'COMPLETED' | 'PAYER_ACTION_REQUIRED';
  expectedAmount: string;
  capturedAmount: string;
  captureCount: number;
  captureIds: string[];
  captureAttempts: number;
  createdAt: string;
}

export interface DemoRefund {
  refundId: string;
  orderId: string;
  amount: string;
  createdAt: string;
}

export interface DemoShopState {
  appName: string;
  orders: DemoOrder[];
  totalOrdersCreated: number;
  totalCapturesRecorded: number;
  totalCapturedAmount: string;
  totalRefundsIssued: number;
  totalRefundAmount: string;
  refunds: DemoRefund[];
  webhookEventsProcessed: string[];
  totalWebhooksProcessed: number;
  currency: string;
}

class StateStore {
  private orders: Map<string, DemoOrder> = new Map();
  private processedWebhooks: Set<string> = new Set();
  private webhookEvents: Array<{ eventId: string; eventType: string; timestamp: string; duplicate: boolean }> = [];
  private refunds: DemoRefund[] = [];

  public recordOrder(orderId: string, amount: string = '38.97'): void {
    this.orders.set(orderId, {
      orderId,
      status: 'CREATED',
      expectedAmount: amount,
      capturedAmount: '0.00',
      captureCount: 0,
      captureIds: [],
      captureAttempts: 0,
      createdAt: new Date().toISOString(),
    });
  }

  public recordCaptureAttempt(orderId: string): void {
    const order = this.orders.get(orderId);
    if (order) {
      order.captureAttempts += 1;
    }
  }

  public getOrder(orderId: string): DemoOrder | undefined {
    return this.orders.get(orderId);
  }

  public recordCaptureSuccess(orderId: string, captureId?: string, amount: string = '38.97'): void {
    const order = this.orders.get(orderId);
    if (order) {
      if (captureId && order.captureIds.includes(captureId)) {
        return;
      }
      order.status = 'COMPLETED';
      order.captureCount += 1;
      if (captureId) {
        order.captureIds.push(captureId);
      }
      const current = parseFloat(order.capturedAmount);
      const added = parseFloat(amount);
      order.capturedAmount = (current + added).toFixed(2);
    }
  }

  public hasWebhookEvent(eventId: string): boolean {
    return this.processedWebhooks.has(eventId);
  }

  public recordWebhookEvent(eventId: string, eventType: string, isDuplicate: boolean = false): void {
    this.processedWebhooks.add(eventId);
    this.webhookEvents.push({
      eventId,
      eventType,
      timestamp: new Date().toISOString(),
      duplicate: isDuplicate,
    });
  }

  public recordRefund(orderId: string, refundId: string, amount: string): void {
    this.refunds.push({
      refundId,
      orderId,
      amount,
      createdAt: new Date().toISOString(),
    });
  }

  public getState(): DemoShopState {
    const orderList = Array.from(this.orders.values());
    const totalCaptured = orderList
      .reduce((sum, o) => sum + parseFloat(o.capturedAmount), 0)
      .toFixed(2);
    const totalRefunded = this.refunds
      .reduce((sum, r) => sum + parseFloat(r.amount), 0)
      .toFixed(2);

    return {
      appName: 'DriftGuard Demo Shop',
      orders: orderList,
      totalOrdersCreated: orderList.length,
      totalCapturesRecorded: orderList.reduce((sum, o) => sum + o.captureCount, 0),
      totalCapturedAmount: totalCaptured,
      totalRefundsIssued: this.refunds.length,
      totalRefundAmount: totalRefunded,
      refunds: [...this.refunds],
      webhookEventsProcessed: Array.from(this.processedWebhooks),
      totalWebhooksProcessed: this.webhookEvents.length,
      currency: 'USD',
    };
  }

  public reset(): void {
    this.orders.clear();
    this.processedWebhooks.clear();
    this.webhookEvents = [];
    this.refunds = [];
  }
}

export const shopState = new StateStore();

