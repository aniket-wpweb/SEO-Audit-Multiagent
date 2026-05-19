"""Resolve TypeScript/JavaScript path aliases from tsconfig.json / jsconfig.json."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.services.repo_layout import join_posix_rel

_SUFFIXES = (".tsx", ".ts", ".jsx", ".js")
_INDEX_NAMES = ("index.tsx", "index.ts", "index.jsx", "index.js")


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _normalize_mapping_target(repo: Path, base_url: Path, target: str) -> str:
    """Turn a paths[] entry into a repo-relative directory prefix (POSIX, no trailing slash)."""
    root = repo.resolve()
    t = target.strip().replace("\\", "/")
    if t.endswith("/*"):
        t = t[:-2]
    if t.startswith("./"):
        resolved = (base_url / t[2:]).resolve()
    elif t.startswith("/"):
        resolved = Path(t)
    else:
        resolved = (base_url / t).resolve()
    try:
        rel = str(resolved.relative_to(root)).replace("\\", "/")
    except ValueError:
        rel = resolved.as_posix()
    return rel.rstrip("/")


def _compile_prefix_mappings(
    repo: Path, paths: dict[str, list[str]], base_url_rel: str
) -> list[tuple[str, str]]:
    """Return (import_prefix, repo_dir_prefix) pairs, longest prefix first."""
    root = repo.resolve()
    base_url = join_posix_rel(root, base_url_rel.replace("\\", "/").strip("/") or ".")
    out: list[tuple[str, str]] = []
    for pattern, targets in paths.items():
        if not isinstance(targets, list) or not targets:
            continue
        if not pattern.endswith("/*"):
            continue
        prefix = pattern[:-2]  # e.g. "@"
        if not prefix:
            continue
        target = targets[0]
        if not isinstance(target, str):
            continue
        dir_prefix = _normalize_mapping_target(root, base_url, target)
        import_prefix = prefix + "/"
        out.append((import_prefix, dir_prefix))
    out.sort(key=lambda x: len(x[0]), reverse=True)
    return out


@lru_cache(maxsize=32)
def load_path_mappings(repo_key: str) -> tuple[tuple[str, str], ...]:
    """Load path alias mappings for a repo (cached by resolved repo path string)."""
    repo = Path(repo_key).resolve()
    mappings: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for name in ("tsconfig.json", "jsconfig.json"):
        data = _read_json(repo / name)
        if not data:
            continue
        compiler = data.get("compilerOptions") or {}
        if not isinstance(compiler, dict):
            continue
        paths = compiler.get("paths") or {}
        if not isinstance(paths, dict):
            continue
        base_url = compiler.get("baseUrl", ".")
        if not isinstance(base_url, str):
            base_url = "."
        for pair in _compile_prefix_mappings(repo, paths, base_url):
            if pair not in seen:
                seen.add(pair)
                mappings.append(pair)
    mappings.sort(key=lambda x: len(x[0]), reverse=True)
    return tuple(mappings)


def _file_candidates(repo: Path, rel_posix: str) -> list[Path]:
    root = repo.resolve()
    base = join_posix_rel(root, rel_posix)
    cands: list[Path] = []
    if base.suffix in _SUFFIXES and base.is_file():
        cands.append(base)
    for ext in _SUFFIXES:
        t = base.with_suffix(ext)
        if t.is_file():
            cands.append(t)
    if base.is_dir():
        for name in _INDEX_NAMES:
            t = base / name
            if t.is_file():
                cands.append(t)
    return cands


def resolve_alias_spec(repo: Path, spec: str) -> str | None:
    """
    Resolve a non-relative import spec (e.g. ``@/components/Blog/SingleBlog``)
    to an existing repo-relative file path, or None.
    """
    spec = spec.strip().replace("\\", "/")
    if not spec or spec.startswith((".", "/")):
        return None
    if "{" in spec or "*" in spec:
        return None

    mappings = load_path_mappings(str(repo.resolve()))
    if not mappings:
        return None

    root = repo.resolve()
    for import_prefix, dir_prefix in mappings:
        if not spec.startswith(import_prefix):
            continue
        rest = spec[len(import_prefix) :]
        rel = f"{dir_prefix}/{rest}" if rest else dir_prefix
        rel = re.sub(r"/+", "/", rel)
        for cand in _file_candidates(root, rel):
            try:
                return str(cand.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
    return None
