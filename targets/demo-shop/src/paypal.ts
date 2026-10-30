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

export const client = new Client({
  clientCredentialsAuthCredentials: {
    oAuthClientId: clientId,
    oAuthClientSecret: clientSecret,
  },
  timeout: 30000,
  environment: Environment.Sandbox,
});

export const ordersController = new OrdersController(client);
export const paymentsController = new PaymentsController(client);
