from __future__ import annotations

import hashlib
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.orchestrator.context import Issue, RunContext
from app.validators.pre_exec import same_origin


def _issue_id(page_url: str, rule_id: str, detail: str) -> str:
    h = hashlib.sha256(f"{page_url}|{rule_id}|{detail}".encode()).hexdigest()[:12]
    return f"{rule_id}_{h}"


def _app_page_tsx_hint(page_url: str) -> str:
    """Map audited page URL to a Next.js App Router ``page.tsx`` path under ``app/``."""
    path = urlparse(page_url).path.rstrip("/") or "/"
    if path == "/":
        return "app/page.tsx"
    segments = [s for s in path.split("/") if s]
    if not segments:
        return "app/page.tsx"
    return "app/" + "/".join(segments) + "/page.tsx"


def _check_link(client: httpx.Client, base_url: str, href: str) -> tuple[bool, str]:
    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return True, "skipped"
    target = urljoin(base_url, href)
    try:
        r = client.head(target, follow_redirects=True, timeout=8.0)
        if r.status_code >= 400:
            return False, str(r.status_code)
        return True, str(r.status_code)
    except Exception:
        try:
            r = client.get(target, follow_redirects=True, timeout=8.0)
            return r.status_code < 400, str(r.status_code)
        except Exception as exc:
            return False, str(exc)


def run(ctx: RunContext) -> None:
    issues: list[Issue] = []
    with httpx.Client(follow_redirects=True) as client:
        for pr in ctx.pages:
            soup = BeautifulSoup(pr.html, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            desc = soup.find("meta", attrs={"name": "description"})
            desc_content = desc.get("content", "").strip() if desc and desc.get("content") else ""

            if not title:
                issues.append(
                    Issue(
                        issue_id=_issue_id(pr.url, "missing_title", ""),
                        rule_id="missing_meta",
                        severity="high",
                        page_url=pr.url,
                        evidence="Missing <title>",
                        suggested_fix="Add a concise <title> in layout or head.",
                        file_hint="app/layout.tsx",
                    )
                )
            if not desc_content:
                issues.append(
                    Issue(
                        issue_id=_issue_id(pr.url, "missing_description", ""),
                        rule_id="missing_meta",
                        severity="high",
                        page_url=pr.url,
                        evidence="Missing meta name=description",
                        suggested_fix="Add export const metadata = { description: '...' } in app/layout.tsx.",
                        file_hint="app/layout.tsx",
                    )
                )

            h1s = soup.find_all("h1")
            if len(h1s) > 1:
                issues.append(
                    Issue(
                        issue_id=_issue_id(pr.url, "dup_h1", str(len(h1s))),
                        rule_id="duplicate_h1",
                        severity="medium",
                        page_url=pr.url,
                        evidence=f"Found {len(h1s)} h1 elements",
                        suggested_fix="Keep a single H1 per page; demote extras to H2.",
                        file_hint=_app_page_tsx_hint(pr.url),
                    )
                )

            for img in soup.find_all("img"):
                alt = img.get("alt")
                if alt is None or (isinstance(alt, str) and not alt.strip() and not img.has_attr("role")):
                    issues.append(
                        Issue(
                            issue_id=_issue_id(pr.url, "img_alt", str(img)),
                            rule_id="missing_alt",
                            severity="medium",
                            page_url=pr.url,
                            evidence=str(img)[:200],
                            suggested_fix="Add meaningful alt text or alt=\"\" if decorative.",
                            file_hint=_app_page_tsx_hint(pr.url),
                        )
                    )

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                target = urljoin(pr.url, href)
                if not target.startswith(("http://", "https://")):
                    continue
                if not same_origin(pr.url, target):
                    # still check external broken links for MVP
                    pass
                ok, detail = _check_link(client, pr.url, href)
                if not ok:
                    issues.append(
                        Issue(
                            issue_id=_issue_id(pr.url, "broken", href),
                            rule_id="broken_link",
                            severity="medium",
                            page_url=pr.url,
                            evidence=f"href={href} ({detail})",
                            suggested_fix="Fix or remove the broken target.",
                            file_hint=None,
                        )
                    )

    ctx.issues = issues
