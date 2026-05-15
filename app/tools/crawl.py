from __future__ import annotations

from collections import deque
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from app.orchestrator.context import PageRecord, RunContext
from app.validators.pre_exec import same_origin


def run(ctx: RunContext) -> None:
    req = ctx.request
    start = req.url
    parsed = urlparse(start)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    pages: list[PageRecord] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        while queue and len(pages) < req.max_pages:
            url, d = queue.popleft()
            if url in seen:
                continue
            if not same_origin(start, url):
                continue
            seen.add(url)
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                status = resp.status if resp else 0
                html = page.content()
            except Exception:
                status = 0
                html = ""
            pages.append(PageRecord(url=url, status_code=status, html=html))
            if d >= req.depth:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                nxt = urljoin(url, a["href"])
                if same_origin(start, nxt) and nxt not in seen and len(seen) + len(queue) < req.max_pages * 3:
                    queue.append((nxt, d + 1))
        browser.close()

    ctx.pages = pages[: req.max_pages]
