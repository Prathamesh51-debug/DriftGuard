"""
Buyer driver: approves a PayPal sandbox order with a headless browser.

Planner Ref: Part 9 (Role C, C2). Spike 3 passed 10/10 (~12s per run).

Given the approval link PayPal returns when an order is created, it logs in as
the sandbox buyer, approves the payment and waits for the redirect to the
order's return URL. It does not capture: the orchestrator captures afterwards,
so the capture call stays visible to the fault-injection proxy.

ApprovalResult is imported from contracts.
"""

import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from contracts import ApprovalResult

from . import paypal_selectors as sel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_RETURN_URL = "http://localhost:3000/return"


def approve_order(
    approve_url: str,
    return_url: str = DEFAULT_RETURN_URL,
    *,
    email: Optional[str] = None,
    password: Optional[str] = None,
    headless: bool = True,
    timeout_s: float = 45.0,
    screenshot_dir: Optional[str] = None,
) -> ApprovalResult:
    """Approve one order as the sandbox buyer. Never raises for page failures."""
    email = email or os.getenv("PAYPAL_SANDBOX_BUYER_EMAIL")
    password = password or os.getenv("PAYPAL_SANDBOX_BUYER_PASSWORD")
    if not email or not password:
        return ApprovalResult(
            approved=False, duration_s=0.0,
            error="PAYPAL_SANDBOX_BUYER_EMAIL / PAYPAL_SANDBOX_BUYER_PASSWORD not set",
        )

    start = time.monotonic()
    timeout_ms = timeout_s * 1000
    shot = None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        page = browser.new_context().new_page()
        page.set_default_timeout(timeout_ms)
        # Nothing has to listen on the return URL; stub it so the redirect resolves.
        page.route(
            f"{return_url}**",
            lambda route: route.fulfill(status=200, content_type="text/html", body="returned"),
        )
        try:
            page.goto(approve_url, wait_until="domcontentloaded")
            page.locator(sel.EMAIL).fill(email)
            # Email and password share one page in some flows, two pages in others.
            if page.locator(sel.NEXT).is_visible():
                page.locator(sel.NEXT).click()
            page.locator(sel.PASSWORD).fill(password)
            page.locator(sel.LOGIN).click()
            submit = page.locator(sel.SUBMIT).first
            submit.wait_for()
            with page.expect_request(lambda r: r.url.startswith(return_url)) as redirect:
                submit.click()
            final_url = redirect.value.url
        except PlaywrightError as exc:
            if screenshot_dir:
                Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
                shot = str(Path(screenshot_dir) / f"approval-failed-{int(time.time())}.png")
                try:
                    page.screenshot(path=shot)
                except PlaywrightError:
                    shot = None
            return ApprovalResult(
                approved=False, duration_s=round(time.monotonic() - start, 2),
                error=str(exc).splitlines()[0], screenshot_path=shot,
            )
        finally:
            browser.close()

    query = parse_qs(urlparse(final_url).query)
    return ApprovalResult(
        approved=True,
        order_id=(query.get("token") or [None])[0],
        payer_id=(query.get("PayerID") or [None])[0],
        return_url=final_url,
        duration_s=round(time.monotonic() - start, 2),
    )