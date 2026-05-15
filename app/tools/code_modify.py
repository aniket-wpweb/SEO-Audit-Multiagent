from __future__ import annotations

import difflib
import os
import re
from pathlib import Path

from app.orchestrator.context import Issue, ModifyResult, RunContext
from app.services.backup import backup_file
from app.services.repo_hints import expand_patch_targets, extract_broken_link_href, resolve_issue_file_hints
from app.services.repo_layout import analyze_repo_layout, join_posix_rel


def _unified_diff(rel_path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
    )


def _patch_layout_description(text: str) -> str | None:
    if "description:" in text:
        return None
    m = re.search(r"export const metadata\s*(?::\s*Metadata)?\s*=\s*\{", text)
    if m:
        insert_at = m.end()
        return text[:insert_at] + "\n  description: 'Sample site for SEO agent workshop'," + text[insert_at:]
    if "<head>" in text:
        return text.replace(
            "<head>",
            '<head>\n<meta name="description" content="Sample site for SEO agent workshop" />',
            1,
        )
    return None


def _patch_page_duplicate_h1(text: str) -> str | None:
    idxs = [m.start() for m in re.finditer(r"<h1\b", text)]
    if len(idxs) < 2:
        return None
    s = idxs[1]
    return text[:s] + "<h2" + text[s + 3 :]


def _patch_page_img_alt(text: str) -> str | None:
    """
    Fix missing or empty ``alt`` on ``<img>`` / Next-rendered tags in source.

    Crawled HTML often has ``alt=""``; the old regex skipped any tag with ``alt=`` present.
    """
    out = text
    orig = text
    out = re.sub(r'\balt=""', 'alt="Workshop image"', out)
    out = re.sub(r"\balt=''", "alt='Workshop image'", out)
    out = re.sub(r'alt="\s+"', 'alt="Workshop image"', out)
    out = re.sub(r"alt='\s+'", "alt='Workshop image'", out)
    # JSX empty string literal (Next ``<Image alt={""} />``)
    out = re.sub(r'alt=\{\s*""\s*\}', 'alt={"Workshop image"}', out)
    out = re.sub(r"alt=\{\s*''\s*\}", "alt={'Workshop image'}", out)
    out, _ = re.subn(
        r"<img(?![^>]*\balt=)([^>]*?)(\s*/?>)",
        r'<img\1 alt="Workshop image"\2',
        out,
    )
    if out != orig:
        return out
    return None


def _patch_broken_internal_href(text: str, bad_href: str) -> str | None:
    """Replace first matching quoted internal href (gated by ``SEO_AGENT_FIX_BROKEN_LINKS``)."""
    if not bad_href.startswith("/"):
        return None
    old = text
    n = text.replace(f'href="{bad_href}"', 'href="/"', 1)
    if n == old:
        n = text.replace(f"href='{bad_href}'", "href='/'", 1)
    if n != old:
        return n
    return None


def _is_jsx_like(rel: str) -> bool:
    return rel.endswith((".tsx", ".jsx"))


def _is_source(rel: str) -> bool:
    return rel.endswith((".tsx", ".ts", ".jsx", ".js")) and not rel.endswith(".d.ts")


def run(ctx: RunContext) -> None:
    req = ctx.request
    if req.dry_run or not req.apply_fixes:
        ctx.modify = ModifyResult(skipped_reason="dry_run_or_apply_off")
        return
    repo = ctx.repo_path
    if repo is None:
        ctx.modify = ModifyResult(skipped_reason="no_repo_path")
        return

    resolve_issue_file_hints(ctx)

    issue_by_file: dict[str, list[Issue]] = {}
    for iss in ctx.issues:
        if iss.file_hint:
            issue_by_file.setdefault(iss.file_hint, []).append(iss)

    diffs: list[str] = []
    touched: list[str] = []
    backups: list[str] = []
    backup_root = repo / ".seo-agent-backups" / ctx.run_id

    def touch_file(rel: str, new_content: str) -> None:
        path = join_posix_rel(repo, rel)
        if not path.is_file():
            return
        before = path.read_text(encoding="utf-8")
        if before == new_content:
            return
        bpath = backup_file(repo, path, backup_root)
        path.write_text(new_content, encoding="utf-8")
        rel_touch = str(path.relative_to(repo)).replace("\\", "/")
        touched.append(rel_touch)
        backups.append(str(bpath))
        diff = _unified_diff(rel_touch, before, new_content)
        if diff.strip():
            diffs.append(diff)

    layout_struct = analyze_repo_layout(repo)
    fix_broken = os.environ.get("SEO_AGENT_FIX_BROKEN_LINKS", "").strip().lower() in ("1", "true", "yes")

    for rel, file_issues in issue_by_file.items():
        if not any(i.rule_id == "missing_meta" for i in file_issues):
            continue
        if not (rel.endswith("layout.tsx") or rel.endswith("layout.jsx")):
            continue
        lp = join_posix_rel(repo, rel)
        if not lp.is_file():
            continue
        before = lp.read_text(encoding="utf-8")
        after = _patch_layout_description(before)
        if after and after != before:
            touch_file(rel, after)

    for rel, file_issues in issue_by_file.items():
        if any(i.rule_id == "missing_meta" for i in file_issues) and (
            rel.endswith("layout.tsx") or rel.endswith("layout.jsx")
        ):
            continue
        if not any(
            i.rule_id in ("duplicate_h1", "missing_alt", "broken_link") for i in file_issues
        ):
            continue

        targets = expand_patch_targets(repo, layout_struct, rel, file_issues)
        for t in targets:
            tp = join_posix_rel(repo, t)
            if not tp.is_file():
                continue
            text = tp.read_text(encoding="utf-8")
            new_text = text

            if any(i.rule_id == "duplicate_h1" for i in file_issues) and _is_jsx_like(t):
                patched = _patch_page_duplicate_h1(new_text)
                if patched:
                    new_text = patched
            if any(i.rule_id == "missing_alt" for i in file_issues) and _is_jsx_like(t):
                patched = _patch_page_img_alt(new_text)
                if patched:
                    new_text = patched
            if fix_broken and any(i.rule_id == "broken_link" for i in file_issues) and _is_source(t):
                for i in file_issues:
                    if i.rule_id != "broken_link":
                        continue
                    bh = extract_broken_link_href(i.evidence)
                    if bh:
                        patched = _patch_broken_internal_href(new_text, bh)
                        if patched:
                            new_text = patched

            if new_text != text:
                touch_file(t, new_text)

    ctx.modify = ModifyResult(diffs=diffs, files_touched=touched, backups=backups)
