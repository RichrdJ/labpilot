"""Render README screenshots from the demo instance (used by the screenshots workflow)."""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

BASE = os.getenv("LABPILOT_URL", "http://127.0.0.1:8080")
OUT = sys.argv[1] if len(sys.argv) > 1 else "docs"


async def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        for name in ("overview", "compute", "storage", "network", "backup"):
            await page.goto(f"{BASE}/#{name}")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=f"{OUT}/{name}.png")
        await page.goto(f"{BASE}/#overview")
        await page.wait_for_timeout(1000)
        await page.keyboard.press("Control+k")
        await page.wait_for_timeout(300)
        await page.keyboard.type("k8s", delay=60)
        await page.wait_for_timeout(400)
        await page.screenshot(path=f"{OUT}/palette.png")
        await page.keyboard.press("Escape")
        await page.evaluate("document.documentElement.dataset.theme = 'light'")
        await page.wait_for_timeout(400)
        await page.screenshot(path=f"{OUT}/light.png")
        await browser.close()


asyncio.run(main())
