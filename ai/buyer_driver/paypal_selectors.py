"""
Every CSS selector the buyer driver uses on PayPal's sandbox approval pages.
Kept in one file so a PayPal page change is a one-file fix.
"""

EMAIL = "#email"
NEXT = "#btnNext"
PASSWORD = "#password"
LOGIN = "#btnLogin"
COOKIE_BANNER = (
    '#acceptAllButton, button#accept-all, #banner-cookie-btn, '
    'button:has-text("Accept Cookies"), button:has-text("Accept All"), '
    'button:has-text("Agree and Continue"), button:has-text("Accept and Continue")'
)
# Review page: PayPal has shown several labels for the final button over time.
# Tightened to exclude cookie consent / banner buttons that may match "Continue".
SUBMIT = (
    '#payment-submit-btn, button#confirmButtonTop, '
    '[data-testid="submit-button-initial"], '
    'button:has-text("Complete Purchase"), '
    'button:has-text("Pay Now"), '
    'button:text-is("Continue"):not([id*="cookie"]):not([class*="cookie"]):not([id*="banner"]):not([id*="gdpr"])'
)
