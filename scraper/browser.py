# scraper/browser.py
"""
Playwright helper that opens a Chromium page.

• Launches with --no-sandbox (needed in many Docker/CI setups)
• Adds --ignore-certificate-errors and ignore_https_errors=True
  so corporate proxy / antivirus MITM certificates don’t block scraping.

Usage
-----
>>> from scraper.browser import get_page
>>> async with get_page(headless=False) as page:
...     await page.goto("https://example.com")
"""
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright

# --------------------------------------------------------------------------- #
# Launch options
# --------------------------------------------------------------------------- #
LAUNCH_ARGS = [
    "--no-sandbox",                 # safer for containers
    "--ignore-certificate-errors",  # skip TLS validation (proxy-friendly)
]

# --------------------------------------------------------------------------- #
# Public helper
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def get_page(headless: bool = True):
    """
    Async context manager that yields a new Playwright Page object.
    The browser is closed automatically when the block exits.
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=LAUNCH_ARGS,
        )

        # Context inherits launch flags; explicit ignore to be safe
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        try:
            yield page
        finally:
            await browser.close()
