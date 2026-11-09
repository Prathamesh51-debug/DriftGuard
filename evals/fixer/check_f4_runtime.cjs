// Exercise checkout's invoice behavior with only PayPal and shop state stubbed.
// Usage: node evals/fixer/check_f4_runtime.cjs path/to/src/checkout.ts
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../../targets/demo-shop/node_modules/typescript');

const calls = [];
let loseFirstResponse = false;
const ordersController = {
  async createOrder(request) {
    calls.push(JSON.parse(JSON.stringify(request)));
    if (loseFirstResponse) {
      loseFirstResponse = false;
      throw Object.assign(new Error('lost response'), { statusCode: 504 });
    }
    return { result: { id: `order-${calls.length}`, links: [] } };
  },
};
const checkout = {};
let randomStep = 0;
const stableMath = Object.create(Math);
stableMath.random = () => ++randomStep / 1000;
const source = fs.readFileSync(path.resolve(process.argv[2]), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText;
vm.runInNewContext(compiled, {
  exports: checkout, process: { env: {} }, setTimeout, console,
  Date: class extends Date { static now() { return 1700000000000; } },
  Math: stableMath,
  require(name) {
    if (name === './paypal') return { ordersController };
    if (name === './state') return { shopState: { recordOrder() {} } };
    if (name === '@paypal/paypal-server-sdk') return {
      CheckoutPaymentIntent: { Capture: 'CAPTURE' }, PaypalExperienceUserAction: { PayNow: 'PAY_NOW' },
    };
    if (name === 'crypto' || name === 'node:crypto') return require(name);
    throw new Error(`Unexpected dependency: ${name}`);
  },
});

function invoice(index) {
  return calls[index].body.purchaseUnits[0].invoiceId;
}

(async () => {
  await checkout.createCheckoutOrder('38.97', { cartId: 'cart-a' });
  await checkout.createCheckoutOrder('38.97', { cartId: 'cart-a' });
  assert.equal(invoice(0), invoice(1), 'same cart changed invoice identity');

  await checkout.createCheckoutOrder('38.97', { cartId: 'cart-b' });
  assert.notEqual(invoice(0), invoice(2), 'distinct equal-price carts share an invoice');

  await checkout.createCheckoutOrder('38.97');
  await checkout.createCheckoutOrder('38.97');
  assert.notEqual(invoice(3), invoice(4), 'separate checkouts with the same clock time share an invoice');

  loseFirstResponse = true;
  await checkout.createCheckoutOrder('38.97', { cartId: 'cart-c' });
  assert.equal(invoice(5), invoice(6), 'retry changed invoice identity');
  assert.deepEqual(calls[5].body, calls[6].body, 'retry changed order body');
  console.log('PASS: same cart stable; equal-price carts and same-time checkouts distinct; retry stable');
})().catch(error => { console.error(error); process.exitCode = 1; });
