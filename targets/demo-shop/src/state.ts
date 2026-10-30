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

export interface DemoShopState {
  appName: string;
  orders: DemoOrder[];
  totalOrdersCreated: number;
  totalCapturesRecorded: number;
  totalCapturedAmount: string;
  currency: string;
}

class StateStore {
  private orders: Map<string, DemoOrder> = new Map();

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

  public recordCaptureSuccess(orderId: string, captureId?: string, amount: string = '38.97'): void {
    const order = this.orders.get(orderId);
    if (order) {
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

  public getState(): DemoShopState {
    const orderList = Array.from(this.orders.values());
    const totalCaptured = orderList
      .reduce((sum, o) => sum + parseFloat(o.capturedAmount), 0)
      .toFixed(2);

    return {
      appName: 'DriftGuard Demo Shop',
      orders: orderList,
      totalOrdersCreated: orderList.length,
      totalCapturesRecorded: orderList.reduce((sum, o) => sum + o.captureCount, 0),
      totalCapturedAmount: totalCaptured,
      currency: 'USD',
    };
  }

  public reset(): void {
    this.orders.clear();
  }
}

export const shopState = new StateStore();

