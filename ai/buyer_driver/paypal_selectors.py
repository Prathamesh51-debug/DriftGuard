"""
Every CSS selector the buyer driver uses on PayPal's sandbox approval pages.
Kept in one file so a PayPal page change is a one-file fix.
"""

EMAIL = "#email"
NEXT = "#btnNext"
PASSWORD = "#password"
LOGIN = "#btnLogin"
# Review page: PayPal has shown several labels for the final button over time.
SUBMIT = (
    '#payment-submit-btn, button:has-text("Complete Purchase"), '
    'button:has-text("Pay Now"), button:has-text("Continue")'
)
