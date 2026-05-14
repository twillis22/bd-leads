"""
Shared Playwright session.

A single browser launch is expensive — ~1-2s. With 34 PlanetBids portals
plus any custom scrapers that also need browsing, we don't want each one
launching its own Chromium.

`BrowserSession` is a small context manager. Use it like:

    with BrowserSession() as session:
        page = session.new_page()
        page.goto(url)
        ...

It also exposes `goto_with_retry` because PlanetBids portals occasionally
hang on first `networkidle` — a second attempt almost always works.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class BrowserSession:
    """Wrap a single Playwright browser + context for reuse across scrapers."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def __enter__(self) -> "BrowserSession":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(user_agent=USER_AGENT)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            # Best-effort teardown — don't mask the original exception
            pass

    def new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("BrowserSession not entered. Use `with BrowserSession() as s:`.")
        return self._context.new_page()

    def goto_with_retry(
        self,
        page: Page,
        url: str,
        wait_selector: str = "tbody tr",
        timeout_ms: int = 45000,
        retries: int = 2,
    ) -> bool:
        """
        Navigate `page` to `url` and wait for `wait_selector`.

        Returns True if the selector appeared, False if all attempts failed.
        Doesn't raise — caller decides what to do with an empty page.
        """
        for attempt in range(retries + 1):
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                page.wait_for_selector(wait_selector, timeout=15000)
                return True
            except PlaywrightTimeoutError:
                if attempt < retries:
                    continue
                return False
            except Exception:
                if attempt < retries:
                    continue
                return False
        return False
