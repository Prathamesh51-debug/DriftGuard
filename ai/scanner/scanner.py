"""
DriftGuard Static Code Scanner.
Analyzes TypeScript, JavaScript, and Python payment repositories to extract
PayPal call sites, identify missing idempotency controls, and generate flow maps.
Planner Ref: Part 9 (Role B3 Scanner).
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Union

from .models import CallSite, FlowMap, RiskType


class CodeScanner:
    """Deterministic static analysis scanner for payment integration vulnerabilities."""

    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        self.project_root = Path(project_root) if project_root else None

    def scan_file(self, file_path: Path) -> List[CallSite]:
        """Scan an individual source file and identify payment call sites and risks."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        rel_path = str(file_path.relative_to(self.project_root)) if self.project_root and file_path.is_relative_to(self.project_root) else file_path.name
        rel_path = rel_path.replace("\\", "/")
        lines = content.splitlines()
        findings: List[CallSite] = []

        # Strip single-line comments for syntax checking so comments like "// Missing paypalRequestId" don't fool the check
        clean_lines = [re.sub(r"//.*$", "", line) for line in lines]

        # 1. Orders Controller / Capture Order Call Sites (SDK & Raw REST API)
        for idx, line in enumerate(lines, 1):
            if re.search(r"ordersController\.(captureOrder|createOrder)|ordersCapture|ordersCreate|v2/checkout/orders", line):
                method = "ordersController.captureOrder" if "capture" in line.lower() else "ordersController.createOrder"
                # Check surrounding context (up to 15 lines before/after) in stripped code
                clean_context = "\n".join(clean_lines[max(0, idx - 15) : min(len(clean_lines), idx + 15)])
                has_idempotency = bool(re.search(r"paypalRequestId\s*[:=]|['\"]PayPal-Request-Id['\"]\s*[:=]", clean_context, re.IGNORECASE))

                risks = []
                if not has_idempotency:
                    risks.append(RiskType.MISSING_IDEMPOTENCY_KEY)

                # Check if retry loop exists around this call
                surrounding = "\n".join(clean_lines[max(0, idx - 10) : min(len(clean_lines), idx + 10)])
                if re.search(r"attempt\s*<=\s*MAX_RETRIES|attempts\s*<=\s*maxRetries|for\s*\(.*attempt|while\s*\(.*attempt", surrounding) and not has_idempotency:
                    risks.append(RiskType.BLIND_RETRY_TIMEOUT)

                findings.append(
                    CallSite(
                        file=rel_path,
                        line=idx,
                        method=method,
                        has_idempotency_key=has_idempotency,
                        risk_types=risks,
                        code_snippet=line.strip(),
                        notes="Idempotency key missing on order operation" if not has_idempotency else "Idempotent PayPal call",
                    )
                )

        # 2. Invoice ID Generation
        for idx, line in enumerate(lines, 1):
            clean_line = clean_lines[idx - 1]
            if re.search(r"invoiceId\s*:|purchaseUnits.*invoice_id", clean_line):
                surrounding = "\n".join(clean_lines[max(0, idx - 2) : min(len(clean_lines), idx + 3)])
                if re.search(r"Math\.random\(\)|uuidv4\(\)|Date\.now\(\)", surrounding):
                    findings.append(
                        CallSite(
                            file=rel_path,
                            line=idx,
                            method="OrderCreation.invoiceId",
                            has_idempotency_key=False,
                            risk_types=[RiskType.NON_DETERMINISTIC_INVOICE],
                            code_snippet=line.strip(),
                            notes="Randomly generated invoice ID causes collisions or breaks reconciliation",
                        )
                    )

        # 3. 422 INSTRUMENT_DECLINED Handling
        for idx, line in enumerate(lines, 1):
            clean_line = clean_lines[idx - 1]
            if re.search(r"INSTRUMENT_DECLINED|422", clean_line):
                surrounding = "\n".join(clean_lines[max(0, idx - 5) : min(len(clean_lines), idx + 15)])
                if "recordCaptureSuccess" in surrounding or re.search(r"status\s*:\s*['\"]COMPLETED['\"]", surrounding):
                    # Check if error marks order completed without returning failure
                    if not re.search(r"if\s*\(.*(422|INSTRUMENT_DECLINED).*\)\s*\{\s*return\s*\{[^}]*success:\s*false", surrounding):
                        findings.append(
                            CallSite(
                                file=rel_path,
                                line=idx,
                                method="CaptureErrorHandler",
                                has_idempotency_key=False,
                                risk_types=[RiskType.UNHANDLED_DECLINE],
                                code_snippet=line.strip(),
                                notes="422 INSTRUMENT_DECLINED handled as successful fulfillment instead of remaining unpaid",
                            )
                        )

        # 4. Money Math & Currency Rounding
        for idx, line in enumerate(lines, 1):
            clean_line = clean_lines[idx - 1]
            if re.search(r"(?:export\s+)?(?:async\s+)?function\s+calculateOrderAmount|const\s+calculateOrderAmount\s*=", clean_line):
                surrounding = "\n".join(clean_lines[max(0, idx - 1) : min(len(clean_lines), idx + 40)])
                risks = []
                if re.search(r"Math\.floor|options\??\.taxRate|discountVal\s*\*|parseFloat.*toFixed", surrounding):
                    risks.append(RiskType.FLOAT_ROUNDING)
                if risks:
                    findings.append(
                        CallSite(
                            file=rel_path,
                            line=idx,
                            method="MoneyMath.calculateOrderAmount",
                            has_idempotency_key=False,
                            risk_types=risks,
                            code_snippet=line.strip(),
                            notes="Floating point precision loss or zero-decimal truncation in currency math",
                        )
                    )

        # 5. Webhook Signature Verification and Deduplication
        for idx, line in enumerate(lines, 1):
            clean_line = clean_lines[idx - 1]
            if re.search(r"(?:export\s+)?(?:async\s+)?function\s+verifyWebhookSignature", clean_line):
                surrounding = "\n".join(clean_lines[max(0, idx - 1) : min(len(clean_lines), idx + 15)])
                risks = []
                if re.search(r"return\s+true\s*;", surrounding) and not re.search(r"paypal-transmission-sig", surrounding):
                    risks.append(RiskType.UNVERIFIED_WEBHOOK)
                if risks:
                    findings.append(
                        CallSite(
                            file=rel_path,
                            line=idx,
                            method="Webhooks.verifySignature",
                            has_idempotency_key=False,
                            risk_types=risks,
                            code_snippet=line.strip(),
                            notes="Missing cryptographic signature verification for incoming PayPal webhooks",
                        )
                    )

            if re.search(r"(?:export\s+)?(?:async\s+)?function\s+handleWebhook\b", clean_line):
                surrounding = "\n".join(clean_lines[max(0, idx - 1) : min(len(clean_lines), idx + 35)])
                if re.search(r"const\s+isDuplicate\s*=\s*false", surrounding) and not re.search(r"if\s*\(.*hasWebhookEvent.*\)\s*return", surrounding):
                    findings.append(
                        CallSite(
                            file=rel_path,
                            line=idx,
                            method="Webhooks.deduplication",
                            has_idempotency_key=False,
                            risk_types=[RiskType.DUPLICATE_WEBHOOK_PROCESSING],
                            code_snippet=line.strip(),
                            notes="Missing idempotent deduplication set for replayed webhook events",
                        )
                    )

        # 6. AI Assistant Guardrails on Financial Operations
        for idx, line in enumerate(lines, 1):
            clean_line = clean_lines[idx - 1]
            if re.search(r"(?:export\s+)?(?:async\s+)?function\s+handleChat\b", clean_line):
                surrounding = "\n".join(clean_lines[max(0, idx - 1) : min(len(clean_lines), idx + 35)])
                if "recordRefund" in surrounding:
                    if not re.search(r"userRole\s*===?\s*['\"]admin['\"]|requestedAmount\s*<=\s*15", surrounding):
                        findings.append(
                            CallSite(
                                file=rel_path,
                                line=idx,
                                method="AIAssistant.refundHandler",
                                has_idempotency_key=False,
                                risk_types=[RiskType.UNGUARDED_AI_REFUND],
                                code_snippet=line.strip(),
                                notes="AI chat assistant triggers refunds without deterministic policy or role checks",
                            )
                        )

        return findings

    def scan(self, target_dir: Union[str, Path]) -> FlowMap:
        """Scan an entire project directory and produce a unified FlowMap."""
        target_path = Path(target_dir).resolve()
        if not self.project_root:
            self.project_root = target_path

        all_sites: List[CallSite] = []
        target_extensions = {".ts", ".js", ".tsx", ".jsx", ".py"}

        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in {"node_modules", "dist", ".git", ".venv", "__pycache__"}]
            for file in sorted(files):
                if Path(file).suffix.lower() in target_extensions:
                    full_file = Path(root) / file
                    sites = self.scan_file(full_file)
                    all_sites.extend(sites)

        vulnerable = sum(1 for s in all_sites if s.risk_types)
        risk_summary = {}
        for s in all_sites:
            for r in s.risk_types:
                risk_summary[r.value] = risk_summary.get(r.value, 0) + 1

        return FlowMap(
            target_path=str(target_path).replace("\\", "/"),
            call_sites=all_sites,
            total_sites=len(all_sites),
            vulnerable_sites=vulnerable,
            risk_summary=risk_summary,
        )


def scan_directory(path: Union[str, Path]) -> FlowMap:
    """Convenience function to scan a directory."""
    scanner = CodeScanner(project_root=path)
    return scanner.scan(path)
