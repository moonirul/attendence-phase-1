
from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


@dataclass
class SessionState:
    running: bool = False
    authenticated: bool = False
    page_url: str | None = None
    title: str | None = None
    started_at: str | None = None
    last_error: str | None = None


class BetopiaBrowserSession:
    """Owns one persistent browser context; login and MFA remain manual."""

    def __init__(
        self,
        profile_dir: str = "./.browser-profile",
        headless: bool = False,
    ):
        self.profile_dir = Path(profile_dir).resolve()
        self.headless = headless

        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

        self._lock = asyncio.Lock()
        self.state = SessionState()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError(
                "Browser session is not running. Start it first."
            )

        return self._page

    async def start(self) -> dict[str, Any]:
        async with self._lock:

            # Reuse an existing browser session.
            if (
                self._context
                and self._page
                and not self._page.is_closed()
            ):
                return await self.status()

            self.profile_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._playwright = await async_playwright().start()

            try:
                self._context = (
                    await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(self.profile_dir),
                        headless=self.headless,
                        viewport={
                            "width": 1440,
                            "height": 960,
                        },
                        accept_downloads=False,
                        args=["--disable-dev-shm-usage"],
                    )
                )

                self._page = (
                    self._context.pages[0]
                    if self._context.pages
                    else await self._context.new_page()
                )

                await self._page.goto(
                    "https://erp.betopiagroup.com/web/login?redirect=%2Fweb%3F",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                from datetime import datetime, timezone

                self.state = SessionState(
                    running=True,
                    authenticated=False,
                    page_url=self._page.url,
                    title=await self._page.title(),
                    started_at=datetime.now(timezone.utc).isoformat(),
                )

                return await self.status()

            except Exception as exc:
                # Capture the actual Playwright error.
                self.state.last_error = (
                    f"{type(exc).__name__}: {exc}"
                )

                print("\nBETOPIA SESSION START FAILED:")
                traceback.print_exc()

                # Clean up failed browser resources.
                if self._context:
                    await self._context.close()

                if self._playwright:
                    await self._playwright.stop()

                self._context = None
                self._page = None

                self.state.running = False
                self.state.authenticated = False

                raise

    async def status(self) -> dict[str, Any]:
        page = self._page

        alive = bool(
            page and not page.is_closed()
        )

        url = page.url if alive else None
        title = await page.title() if alive else None

        # Preliminary URL-based signal only.
        # This does NOT verify actual ERP authentication.
        looks_authenticated = bool(
            alive and "/web/login" not in (url or "")
        )

        self.state.running = alive
        self.state.page_url = url
        self.state.title = title
        self.state.authenticated = looks_authenticated

        return {
            "running": self.state.running,
            "authenticated_hint": self.state.authenticated,
            "authentication_verified": False,
            "page_url": url,
            "title": title,
            "started_at": self.state.started_at,
            "last_error": self.state.last_error,
            "note": (
                "URL-based hint only; not proof of "
                "an authenticated ERP session."
            ),
        }

    async def inspect(self) -> dict[str, Any]:
        page = self.page

        if page.is_closed():
            raise RuntimeError("Browser page is closed.")

        return await page.evaluate("""() => {
          const visible = (el) => {
            const s = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();

            return (
              s.visibility !== 'hidden' &&
              s.display !== 'none' &&
              r.width > 0 &&
              r.height > 0
            );
          };

          const text = (el) => (
            el.innerText ||
            el.getAttribute('aria-label') ||
            el.title ||
            ''
          ).trim();

          const buttons = [
            ...document.querySelectorAll(
              'button, input[type=button], input[type=submit], [role=button]'
            )
          ]
            .filter(visible)
            .map(el => ({
              tag: el.tagName.toLowerCase(),
              role:
                el.getAttribute('role') ||
                (el.tagName === 'BUTTON' ? 'button' : null),
              accessible_name_candidate:
                text(el) || el.value || null,
              aria_label: el.getAttribute('aria-label'),
              title: el.getAttribute('title'),
              disabled:
                !!el.disabled ||
                el.getAttribute('aria-disabled') === 'true',
              id: el.id || null,
              class_name:
                typeof el.className === 'string'
                  ? el.className
                  : null
            }));

          const inputs = [
            ...document.querySelectorAll(
              'input, textarea, select'
            )
          ]
            .filter(visible)
            .map(el => {
              const labels = [
                ...(el.labels || [])
              ]
                .map(x => text(x))
                .filter(Boolean);

              return {
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type'),
                name: el.getAttribute('name'),
                id: el.id || null,
                labels,
                aria_label: el.getAttribute('aria-label'),
                placeholder: el.getAttribute('placeholder'),
                disabled: !!el.disabled
              };
            });

          const statusCandidates = [
            ...document.querySelectorAll(
              '[role=status], [role=alert], time, .badge, .o_tag, [class*=status], [class*=attendance]'
            )
          ]
            .filter(visible)
            .map(el => ({
              tag: el.tagName.toLowerCase(),
              role: el.getAttribute('role'),
              text: text(el).slice(0, 300),
              id: el.id || null,
              class_name:
                typeof el.className === 'string'
                  ? el.className
                  : null
            }))
            .filter(x => x.text);

          const bodyText = (
            document.body?.innerText || ''
          ).slice(0, 12000);

          const expirationTerms = [
            'session expired',
            'session has expired',
            'log in again',
            'authentication required',
            'access denied'
          ];

          return {
            inspected_at: new Date().toISOString(),
            url: location.href,
            title: document.title,
            buttons,
            inputs,
            status_candidates: statusCandidates,
            session_expiration_text_matches:
              expirationTerms.filter(
                t => bodyText.toLowerCase().includes(t)
              ),
            body_text_excerpt: bodyText
          };
        }""")

    async def stop(self) -> None:
        async with self._lock:

            if self._context:
                await self._context.close()

            if self._playwright:
                await self._playwright.stop()

            self._context = None
            self._page = None

            self.state.running = False
            self.state.authenticated = False
