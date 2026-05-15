from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


def join_posix_rel(root: Path, posix_rel: str) -> Path:
    rel = posix_rel.replace("\\", "/").strip("/")
    if not rel:
        return root
    return root.joinpath(*rel.split("/"))


@dataclass(frozen=True)
class RepoLayout:
    """Detected Next-style source roots under the repository root (POSIX segments)."""

    app_dir: str | None  # e.g. "app" or "src/app"
    pages_dir: str | None  # e.g. "pages" or "src/pages"


def analyze_repo_layout(repo: Path) -> RepoLayout:
    root = repo.resolve()
    app_dir = None
    for rel in ("src/app", "app"):
        if join_posix_rel(root, rel).is_dir():
            app_dir = rel
            break
    pages_dir = None
    for rel in ("src/pages", "pages"):
        if join_posix_rel(root, rel).is_dir():
            pages_dir = rel
            break
    return RepoLayout(app_dir=app_dir, pages_dir=pages_dir)


def _path_segments_from_url(page_url: str) -> list[str]:
    path = urlparse(page_url).path.rstrip("/") or "/"
    if path == "/":
        return []
    return [s for s in path.split("/") if s]


def app_router_page_candidates(repo: Path, layout: RepoLayout, page_url: str) -> list[str]:
    """Return existing App Router page files (posix rel paths), most specific first."""
    if not layout.app_dir:
        return []
    root = repo.resolve()
    segs = _path_segments_from_url(page_url)
    base = join_posix_rel(root, layout.app_dir)
    dir_path = base.joinpath(*segs) if segs else base
    trials: list[Path] = []
    for name in ("page.tsx", "page.jsx", "page.ts"):
        trials.append(dir_path / name)
    out: list[str] = []
    for p in trials:
        if p.is_file():
            rel = str(p.relative_to(root)).replace("\\", "/")
            if rel not in out:
                out.append(rel)
    return out


def pages_router_page_candidates(repo: Path, layout: RepoLayout, page_url: str) -> list[str]:
    """Return existing Pages Router entry files for the URL path."""
    if not layout.pages_dir:
        return []
    root = repo.resolve()
    segs = _path_segments_from_url(page_url)
    base = join_posix_rel(root, layout.pages_dir)
    candidates: list[Path] = []
    if not segs:
        for name in ("index.tsx", "index.jsx", "index.js"):
            candidates.append(base / name)
    else:
        parent = base.joinpath(*segs[:-1]) if len(segs) > 1 else base
        leaf = segs[-1]
        candidates.append(parent / f"{leaf}.tsx")
        candidates.append(parent / f"{leaf}.jsx")
        candidates.append(base.joinpath(*segs) / "index.tsx")
        candidates.append(base.joinpath(*segs) / "index.jsx")
    out: list[str] = []
    for p in candidates:
        if p.is_file():
            rel = str(p.relative_to(root)).replace("\\", "/")
            if rel not in out:
                out.append(rel)
    return out


def layout_file_candidates(repo: Path, layout: RepoLayout) -> list[str]:
    out: list[str] = []
    if not layout.app_dir:
        return out
    root = repo.resolve()
    app = join_posix_rel(root, layout.app_dir)
    for name in ("layout.tsx", "layout.jsx"):
        p = app / name
        if p.is_file():
            out.append(str(p.relative_to(root)).replace("\\", "/"))
    return out


def normalize_audit_file_hint(repo: Path, layout: RepoLayout, hint: str) -> str | None:
    """If ``hint`` exists in the repo, return it; else try workshop ``app/`` ↔ ``src/app/`` swap."""
    root = repo.resolve()
    hint = hint.replace("\\", "/")
    p = join_posix_rel(root, hint)
    if p.is_file():
        return hint
    if hint.startswith("app/") and layout.app_dir == "src/app":
        alt = "src/app/" + hint[4:]
        ap = join_posix_rel(root, alt)
        if ap.is_file():
            return alt
    if hint.startswith("src/app/") and layout.app_dir == "app":
        alt = "app/" + hint[8:]
        ap = join_posix_rel(root, alt)
        if ap.is_file():
            return alt
    return None


def resolve_page_source_file(repo: Path, layout: RepoLayout, stack_label: str, page_url: str) -> str | None:
    """Pick the best on-disk source file for ``page_url`` (App Router preferred, then Pages)."""
    app_c = app_router_page_candidates(repo, layout, page_url)
    if app_c:
        return app_c[0]
    if stack_label == "nextjs" or layout.pages_dir:
        pg = pages_router_page_candidates(repo, layout, page_url)
        if pg:
            return pg[0]
    return None


def scan_roots_for_grep(layout: RepoLayout) -> list[str]:
    roots: list[str] = []
    if layout.app_dir:
        roots.append(layout.app_dir)
    if layout.pages_dir:
        roots.append(layout.pages_dir)
    return roots
