
import asyncio
import sys
import traceback

from playwright.async_api import async_playwright


async def main():
    print("Python:", sys.version)
    print("Event loop:", type(asyncio.get_running_loop()).__name__)

    try:
        async with async_playwright() as p:
            print("Playwright initialized")

            browser = await p.chromium.launch(headless=False)

            print("Chromium launched successfully")

            page = await browser.new_page()
            await page.goto("https://example.com")

            print("Page title:", await page.title())

            await browser.close()

    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
