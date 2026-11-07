// Execute the real checkout source; replace only the external SDK/state boundaries.
// Usage: node evals/fixer/check_f2_runtime.cjs path/to/src/checkout.ts
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../../targets/demo-shop/node_modules/typescript');

const calls = [];
const recorded = [];
const ordersController = {
  async createOrder(request) {
    calls.push(JSON.parse(JSON.stringify(request)));
    if (calls.length % 2 === 1) throw Object.assign(new Error('lost response'), { statusCode: 504 });
    return { result: { id: `order-${calls.length / 2}`, links: [] } };
  },
};
const exportsObject = {};
const source = fs.readFileSync(path.resolve(process.argv[2]), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
vm.runInNewContext(compiled, {
  exports: exportsObject, process: { env: {} }, setTimeout, console,
  require(name) {
    if (name === './paypal') return { ordersController };
    if (name === './state') return { shopState: { recordOrder: (...args) => recorded.push(args) } };
    if (name === '@paypal/paypal-server-sdk') return {
      CheckoutPaymentIntent: { Capture: 'CAPTURE' }, PaypalExperienceUserAction: { PayNow: 'PAY_NOW' },
    };
    if (name === 'crypto' || name === 'node:crypto') return require(name);
    throw new Error(`Unexpected dependency: ${name}`);
  },
});

(async () => {
  await exportsObject.createCheckoutOrder('38.97');
  await exportsObject.createCheckoutOrder('38.97');
  assert.equal(calls.length, 4, 'each purchase must retry the lost response once');
  for (const start of [0, 2]) {
    assert.ok(calls[start].paypalRequestId, 'request ID is required');
    assert.equal(calls[start].paypalRequestId, calls[start + 1].paypalRequestId, 'retry changed request ID');
    assert.deepEqual(calls[start].body, calls[start + 1].body, 'retry changed order body');
  }
  assert.notEqual(calls[0].paypalRequestId, calls[2].paypalRequestId, 'equal-price purchases reused an ID');
  assert.equal(recorded.length, 2, 'record each completed purchase once');
  console.log('PASS: stable retry key/body; separate equal-price purchases use distinct keys');
})().catch(error => { console.error(error); process.exitCode = 1; });
