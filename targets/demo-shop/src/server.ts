import express, { Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { createCheckoutOrder, captureCheckoutOrder } from './checkout';
import { handleWebhook } from './webhooks';
import { handleChat } from './assistant';
import { shopState } from './state';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = parseInt(process.env.DEMO_SHOP_PORT || '3001', 10);

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../public')));

/**
 * Health check endpoint
 */
app.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'ok',
    app: 'driftguard-demo-shop',
    timestamp: new Date().toISOString(),
  });
});

/**
 * DriftGuard State Inspection Endpoint
 * Queried by the Reconciler to verify internal application drift against PayPal.
 */
app.get(['/_driftguard/state', '/driftguard/state'], (_req: Request, res: Response) => {
  res.json(shopState.getState());
});

/**
 * Reset internal state for test resets
 */
app.post(['/_driftguard/reset', '/driftguard/reset'], (_req: Request, res: Response) => {
  shopState.reset();
  res.json({ status: 'reset', state: shopState.getState() });
});

/**
 * Create Order Endpoint
 * Called by checkout UI or orchestrator runner.
 */
app.post('/api/orders', async (req: Request, res: Response) => {
  try {
    const amount = req.body?.amount || '38.97';
    const options = req.body?.options;
    const result = await createCheckoutOrder(amount, options);
    res.status(201).json(result);
  } catch (error: any) {
    console.error('[DemoShop] Create order error:', error);
    res.status(500).json({
      error: 'ORDER_CREATION_FAILED',
      message: error?.message || 'Failed to create PayPal order',
    });
  }
});

/**
 * Capture Order Endpoint
 * Contains BUG-01 vulnerability (blind retry on network timeout).
 */
app.post('/api/orders/:id/capture', async (req: Request, res: Response) => {
  try {
    const orderId = req.params.id;
    const result = await captureCheckoutOrder(orderId);
    if (result.success) {
      res.status(200).json(result);
    } else {
      res.status(502).json(result);
    }
  } catch (error: any) {
    console.error('[DemoShop] Capture error:', error);
    res.status(500).json({
      error: 'CAPTURE_FAILED',
      message: error?.message || 'Failed to capture PayPal order',
    });
  }
});

/**
 * Webhook Ingestion Endpoint
 * Receives incoming PayPal notifications (BUG-08 unverified signature, BUG-09 duplicate replay).
 */
app.post('/api/webhooks', handleWebhook);

/**
 * AI Customer Support Chat Endpoint
 * Evaluated by F7 prompt injection attacks (BUG-10 unauthorized refund bypass).
 */
app.post('/api/chat', handleChat);

app.listen(port, () => {
  console.log(`[DemoShop] DriftGuard Demo Shop listening at http://localhost:${port}`);
  console.log(`[DemoShop] Internal state endpoint: http://localhost:${port}/_driftguard/state`);
});

export default app;

