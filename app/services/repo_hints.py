from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from app.orchestrator.context import Issue, RunContext
from app.services.repo_layout import (
    RepoLayout,
    analyze_repo_layout,
    join_posix_rel,
    layout_file_candidates,
    normalize_audit_file_hint,
    resolve_page_source_file,
    scan_roots_for_grep,
)
from app.validators.pre_exec import same_origin

_REL_IMPORT_RE = re.compile(
    r"""from\s+['"](\.\.?/[^'"]+)['"]|import\s*\(\s*['"](\.\.?/[^'"]+)['"]\s*\)""",
)


def extract_broken_link_href(evidence: str) -> str | None:
    """Public wrapper for href parsing from audit evidence."""
    return _extract_href_from_broken_link_evidence(evidence)


def _extract_href_from_broken_link_evidence(evidence: str) -> str | None:
    if not evidence.startswith("href="):
        return None
    rest = evidence[5:]
    i = rest.rfind(" (")
    if i == -1:
        return rest.strip() or None
    return rest[:i].strip() or None


def _href_to_path_for_mapping(page_url: str, href: str) -> str | None:
    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    if href.startswith(("http://", "https://")):
        if not same_origin(page_url, href):
            return None
        p = urlparse(href).path
        return p if p else "/"
    joined = urljoin(page_url, href)
    path = urlparse(joined).path
    return path if path else "/"


def _evidence_substrings_for_grep(evidence: str) -> list[str]:
    """Pull a few stable substrings from audit evidence (img src, long paths)."""
    out: list[str] = []
    for m in re.finditer(r'src=["\']([^"\']+)["\']', evidence):
        s = m.group(1).strip()
        if len(s) >= 8:
            out.append(s)
    for m in re.finditer(r"url=([^&\s\"']+)", evidence):
        s = m.group(1).strip()
        if len(s) >= 8:
            out.append(s)
    if len(evidence) >= 12 and "<" in evidence:
        chunk = evidence.strip()
        if len(chunk) > 200:
            chunk = chunk[:200]
        out.append(chunk)
    seen: set[str] = set()
    dedup: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            dedup.append(s)
    return dedup[:5]


def grep_repo_for_substring(
    repo: Path,
    layout: RepoLayout,
    needle: str,
    *,
    max_files_scanned: int = 400,
    max_hits: int = 25,
) -> list[str]:
    if len(needle) < 4:
        return []
    root = repo.resolve()
    hits: list[str] = []
    scanned = 0
    suffixes = (".tsx", ".ts", ".jsx", ".js")
    for root_rel in scan_roots_for_grep(layout):
        base = join_posix_rel(root, root_rel)
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in suffixes:
                continue
            scanned += 1
            if scanned > max_files_scanned:
                return hits
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if needle in text:
                rel = str(p.relative_to(root)).replace("\\", "/")
                if rel not in hits:
                    hits.append(rel)
                if len(hits) >= max_hits:
                    return hits
    return hits


def _resolve_import_to_file(repo: Path, from_file: Path, spec: str) -> Path | None:
    root = repo.resolve()
    if "/node_modules/" in spec or "node_modules" in spec:
        return None
    cand = (from_file.parent / spec).resolve()
    try:
        cand.relative_to(root)
    except ValueError:
        return None
    if cand.is_file() and cand.suffix in (".tsx", ".ts", ".jsx", ".js"):
        return cand
    for ext in (".tsx", ".ts", ".jsx", ".js"):
        t = cand.with_suffix(ext)
        if t.is_file():
            return t
    if cand.is_dir():
        for name in ("index.tsx", "index.ts", "index.jsx"):
            t = cand / name
            if t.is_file():
                return t
    return None


def collect_import_neighbors(
    repo: Path,
    entry_rel: str,
    *,
    max_depth: int = 4,
    max_files: int = 20,
) -> list[str]:
    """Bounded static relative-import walk from ``entry_rel`` (BFS)."""
    root = repo.resolve()
    entry_rel = entry_rel.replace("\\", "/")
    visited: set[str] = set()
    order: list[str] = []
    frontier: list[tuple[str, int]] = [(entry_rel, 0)]

    while frontier and len(order) < max_files:
        cur, depth = frontier.pop(0)
        if cur in visited:
            continue
        visited.add(cur)
        order.append(cur)
        if depth >= max_depth:
            continue
        path = join_posix_rel(root, cur)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _REL_IMPORT_RE.finditer(text):
            spec = (m.group(1) or m.group(2) or "").strip()
            if not spec or "{" in spec or "*" in spec:
                continue
            resolved = _resolve_import_to_file(repo, path, spec)
            if resolved is None:
                continue
            rrel = str(resolved.relative_to(root)).replace("\\", "/")
            if rrel not in visited and len(order) + len(frontier) < max_files * 2:
                frontier.append((rrel, depth + 1))
    return order


def expand_patch_targets(
    repo: Path,
    layout: RepoLayout,
    entry_rel: str,
    file_issues: list[Issue],
    *,
    max_files: int = 25,
) -> list[str]:
    """Primary route file plus import neighbors and bounded evidence / href grep hits."""
    entry_rel = entry_rel.replace("\\", "/")
    pool: list[str] = [entry_rel]
    rules = {i.rule_id for i in file_issues}
    if rules & {"missing_alt", "duplicate_h1", "broken_link"}:
        pool.extend(collect_import_neighbors(repo, entry_rel, max_depth=4, max_files=max_files))
    for i in file_issues:
        if i.rule_id == "missing_alt":
            for tok in _evidence_substrings_for_grep(i.evidence):
                pool.extend(grep_repo_for_substring(repo, layout, tok, max_hits=8))
        if i.rule_id == "broken_link":
            h = _extract_href_from_broken_link_evidence(i.evidence)
            if h and len(h) > 3:
                pool.extend(grep_repo_for_substring(repo, layout, h, max_hits=8))
    seen: set[str] = set()
    ordered: list[str] = []
    for r in pool:
        r = r.replace("\\", "/")
        if r in seen:
            continue
        seen.add(r)
        ordered.append(r)
        if len(ordered) >= max_files:
            break
    return ordered


def _resolve_broken_link_hint(
    repo: Path,
    layout: RepoLayout,
    stack_label: str,
    iss: Issue,
) -> str | None:
    href = _extract_href_from_broken_link_evidence(iss.evidence)
    if not href:
        return None
    hits = grep_repo_for_substring(repo, layout, href, max_hits=12)
    if hits:
        return hits[0]
    path = _href_to_path_for_mapping(iss.page_url, href)
    if path is None:
        return None
    pu = urlparse(iss.page_url)
    norm = path if path.startswith("/") else "/" + path
    synthetic = urlunparse((pu.scheme, pu.netloc, norm, "", "", ""))
    return resolve_page_source_file(repo, layout, stack_label, synthetic)


def resolve_issue_file_hints(ctx: RunContext) -> None:
    """Rewrite ``file_hint`` using on-disk layout, stack label, and bounded search."""
    repo = ctx.repo_path
    if repo is None:
        return
    layout = analyze_repo_layout(repo)
    stack_label = ctx.stack.label if ctx.stack else "unknown"
    layouts = layout_file_candidates(repo, layout)
    new_issues: list[Issue] = []

    for iss in ctx.issues:
        hint = iss.file_hint
        if iss.rule_id == "missing_meta":
            if layouts:
                chosen = None
                if hint:
                    chosen = normalize_audit_file_hint(repo, layout, hint)
                nh = chosen or layouts[0]
                new_issues.append(iss if nh == hint else iss.model_copy(update={"file_hint": nh}))
                continue
            new_issues.append(iss)
            continue

        if iss.rule_id in ("duplicate_h1", "missing_alt"):
            if hint:
                norm = normalize_audit_file_hint(repo, layout, hint)
                if norm:
                    new_issues.append(iss if norm == hint else iss.model_copy(update={"file_hint": norm}))
                    continue
            resolved = resolve_page_source_file(repo, layout, stack_label, iss.page_url)
            if resolved and resolved != hint:
                new_issues.append(iss.model_copy(update={"file_hint": resolved}))
            else:
                new_issues.append(iss)
            continue

        if iss.rule_id == "broken_link":
            nh = _resolve_broken_link_hint(repo, layout, stack_label, iss)
            if nh and nh != hint:
                new_issues.append(iss.model_copy(update={"file_hint": nh}))
            else:
                new_issues.append(iss)
            continue

        if hint:
            norm = normalize_audit_file_hint(repo, layout, hint)
            if norm and norm != hint:
                new_issues.append(iss.model_copy(update={"file_hint": norm}))
                continue
        new_issues.append(iss)

    ctx.issues = new_issues
