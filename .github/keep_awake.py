"""Open the deployed app in a headless browser; if Streamlit Cloud shows the sleep page, wake the app up."""
import os
import sys
import time

from playwright.sync_api import sync_playwright

url = os.environ.get("APP_URL", "")
if not url or "YOUR-APP-NAME" in url:
    print("Set APP_URL in .github/workflows/keep-awake.yml to your app's address.")
    sys.exit(0)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(url, timeout=120_000)
    time.sleep(10)
    wake = page.get_by_role("button", name="Yes, get this app back up!")
    if wake.count():
        wake.first.click()
        print("The app was asleep. Woke it up.")
        time.sleep(90)
    else:
        print("The app is awake.")
    browser.close()
