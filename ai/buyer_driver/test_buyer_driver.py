import pytest
from playwright.sync_api import sync_playwright
from ai.buyer_driver import paypal_selectors as sel


def test_submit_selector_ignores_cookie_consent_buttons():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("""
            <html>
                <body>
                    <div id="consent-layer">
                        <button class="btn-primary">Agree and Continue</button>
                        <button class="cookie-btn">Continue</button>
                        <button id="banner-btn">Continue</button>
                    </div>
                    <div id="review-layer">
                        <button id="payment-submit-btn">Pay Now</button>
                    </div>
                </body>
            </html>
        """)
        submit_btn = page.locator(sel.SUBMIT).first
        assert submit_btn.text_content().strip() == "Pay Now"
        browser.close()


def test_submit_selector_matches_exact_continue_button():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("""
            <html>
                <body>
                    <button class="cookie-accept">Agree and Continue</button>
                    <button id="confirmButtonTop">  Continue  </button>
                </body>
            </html>
        """)
        submit_btn = page.locator(sel.SUBMIT).first
        assert submit_btn.text_content().strip() == "Continue"
        browser.close()


def test_cookie_banner_selector_matches_consent_buttons():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("""
            <html>
                <body>
                    <button class="btn">Agree and Continue</button>
                </body>
            </html>
        """)
        cookie_btn = page.locator(sel.COOKIE_BANNER).first
        assert cookie_btn.is_visible()
        browser.close()
