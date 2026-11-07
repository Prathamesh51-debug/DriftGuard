"""
Tests for DriftGuard Static Code Scanner.
Validates call site extraction, idempotency checking, and vulnerability detection.
"""

from pathlib import Path
import pytest

from ai.scanner import CodeScanner, FlowMap, RiskType, scan_directory


DEMO_SHOP_SRC = Path(__file__).resolve().parents[3] / "targets" / "demo-shop" / "src"


def test_scan_demo_shop_detects_seeded_risks():
    scanner = CodeScanner(project_root=DEMO_SHOP_SRC.parent)
    flow_map = scanner.scan(DEMO_SHOP_SRC)

    assert isinstance(flow_map, FlowMap)
    assert flow_map.total_sites >= 7
    assert flow_map.vulnerable_sites >= 7

    detected_risks = set(flow_map.risk_summary.keys())
    assert RiskType.MISSING_IDEMPOTENCY_KEY.value in detected_risks
    assert RiskType.BLIND_RETRY_TIMEOUT.value in detected_risks
    assert RiskType.UNHANDLED_DECLINE.value in detected_risks
    assert RiskType.NON_DETERMINISTIC_INVOICE.value in detected_risks
    assert RiskType.FLOAT_ROUNDING.value in detected_risks
    assert RiskType.UNVERIFIED_WEBHOOK.value in detected_risks
    assert RiskType.DUPLICATE_WEBHOOK_PROCESSING.value in detected_risks
    assert RiskType.UNGUARDED_AI_REFUND.value in detected_risks


def test_clean_idempotent_order_not_flagged(tmp_path):
    clean_code = """
    export async function createSafeOrder(orderId: string) {
      const idempotencyKey = crypto.createHash('sha256').update(orderId).digest('hex');
      const { result } = await ordersController.createOrder({
        paypalRequestId: idempotencyKey,
        body: { intent: 'CAPTURE' }
      });
      return result;
    }
    """
    safe_file = tmp_path / "safe.ts"
    safe_file.write_text(clean_code, encoding="utf-8")

    scanner = CodeScanner(project_root=tmp_path)
    sites = scanner.scan_file(safe_file)

    assert len(sites) == 1
    site = sites[0]
    assert site.has_idempotency_key is True
    assert site.risk_types == []


def test_clean_webhook_verification_not_flagged(tmp_path):
    clean_code = """
    export async function verifyWebhookSignature(req: Request): Promise<boolean> {
      const sig = req.headers['paypal-transmission-sig'];
      const certUrl = req.headers['paypal-cert-url'];
      if (!sig || !certUrl) return false;
      return true;
    }
    """
    safe_file = tmp_path / "safe_wh.ts"
    safe_file.write_text(clean_code, encoding="utf-8")

    scanner = CodeScanner(project_root=tmp_path)
    sites = scanner.scan_file(safe_file)

    assert len(sites) == 0 or all(RiskType.UNVERIFIED_WEBHOOK not in s.risk_types for s in sites)


def test_convenience_scan_directory():
    flow_map = scan_directory(DEMO_SHOP_SRC)
    assert flow_map.total_sites >= 7
    assert flow_map.vulnerable_sites >= 7

