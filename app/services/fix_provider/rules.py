from __future__ import annotations

import re
from urllib.parse import urlparse

from app.orchestrator.context import Issue
from app.services.fix_provider.base import FixFileResult, FixProvider
from app.services.repo_stack import RepoStackInfo


def _site_label(site_url: str) -> str:
    host = urlparse(site_url).netloc or "site"
    return host.replace("www.", "").split(":")[0] or "site"


class RulesProvider(FixProvider):
    name = "rules"

    def __init__(self, site_url: str) -> None:
        self._site_url = site_url
        self._label = _site_label(site_url)

    def fix_file(
        self,
        *,
        rel_path: str,
        content: str,
        issues: list[Issue],
        repo_stack: RepoStackInfo,
        site_url: str,
    ) -> FixFileResult:
        new_text = content
        rules = {i.rule_id for i in issues}

        if "missing_meta" in rules and (rel_path.endswith("layout.tsx") or rel_path.endswith("layout.jsx")):
            patched = self._patch_layout_description(new_text)
            if patched:
                new_text = patched

        if "duplicate_h1" in rules and rel_path.endswith((".tsx", ".jsx", ".html")):
            patched = self._patch_duplicate_h1(new_text)
            if patched:
                new_text = patched

        if "missing_alt" in rules and rel_path.endswith((".tsx", ".jsx", ".html")):
            patched = self._patch_img_alt(new_text)
            if patched:
                new_text = patched

        if new_text == content:
            return FixFileResult(content=None, reason="no_rule_match", provider=self.name)
        return FixFileResult(content=new_text, reason="ok", provider=self.name)

    def _patch_layout_description(self, text: str) -> str | None:
        if "description:" in text and 'name="description"' not in text:
            if re.search(r"description:\s*['\"][^'\"]+['\"]", text):
                return None
        desc = f"Page for {self._label}"
        m = re.search(r"export const metadata\s*(?::\s*Metadata)?\s*=\s*\{", text)
        if m:
            insert_at = m.end()
            return text[:insert_at] + f"\n  description: '{desc}'," + text[insert_at:]
        if "<head>" in text and 'name="description"' not in text:
            return text.replace(
                "<head>",
                f'<head>\n<meta name="description" content="{desc}" />',
                1,
            )
        return None

    @staticmethod
    def _patch_duplicate_h1(text: str) -> str | None:
        idxs = [m.start() for m in re.finditer(r"<h1\b", text, re.I)]
        if len(idxs) < 2:
            return None
        s = idxs[1]
        return text[:s] + "<h2" + text[s + 3 :]

    @staticmethod
    def _patch_img_alt(text: str) -> str | None:
        label = "Page image"
        out = text
        orig = text
        out = re.sub(r'\balt=""', f'alt="{label}"', out)
        out = re.sub(r"\balt=''", f"alt='{label}'", out)
        out = re.sub(r'alt=\{\s*""\s*\}', f'alt={{"{label}"}}', out)
        out, _ = re.subn(
            r"<img(?![^>]*\balt=)([^>]*?)(\s*/?>)",
            rf'<img\1 alt="{label}"\2',
            out,
            flags=re.I,
        )
        out, _ = re.subn(
            r"<Image(?![^>]*\balt=)([^>]*?)(\s*/?>)",
            rf'<Image\1 alt="{label}"\2',
            out,
            flags=re.I,
        )
        return out if out != orig else None
