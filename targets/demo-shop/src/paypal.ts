import { Client, Environment, OrdersController, PaymentsController } from '@paypal/paypal-server-sdk';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load root .env file if available, fall back to process environment
dotenv.config({ path: path.resolve(__dirname, '../../../.env') });
dotenv.config();

const clientId = process.env.PAYPAL_CLIENT_ID || '';
const clientSecret = process.env.PAYPAL_CLIENT_SECRET || '';
const proxyHost = process.env.PROXY_HOST || '127.0.0.1';
const proxyPort = parseInt(process.env.PROXY_PORT || '8080', 10);
const useProxy = process.env.USE_PROXY === 'true';

if (useProxy) {
  // Allow Node.js to trust the local mitmproxy interceptor CA certificate
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
}

export const client = new Client({
  clientCredentialsAuthCredentials: {
    oAuthClientId: clientId,
    oAuthClientSecret: clientSecret,
  },
  timeout: 30000,
  environment: Environment.Sandbox,
  ...(useProxy ? {
    httpClientOptions: {
      proxySettings: {
        address: `http://${proxyHost}`,
        port: proxyPort,
      },
    },
  } : {}),
});

export const ordersController = new OrdersController(client);
export const paymentsController = new PaymentsController(client);
