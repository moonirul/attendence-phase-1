"""Manual authentication helpers. No credentials are collected or automated."""

from playwright.async_api import Page


async def open_login(page: Page) -> None:
    await page.goto(
        "https://erp.betopiagroup.com/web/login?redirect=%2Fweb%3F",
        wait_until="domcontentloaded",
        timeout=60000,
    )


async def wait_for_manual_login(page: Page, timeout_ms: int = 180_000) -> bool:
    """Wait for the user to finish login/MFA; URL change is a hint, not proof."""
    try:
        await page.wait_for_url(
            lambda url: "/web/login" not in str(url),
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False
