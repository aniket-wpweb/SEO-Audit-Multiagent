"""Resolve and validate repo_root against SEO_AGENT_REPO_ALLOWLIST."""

from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    """seo-agent/ directory (parent of app/)."""
    return Path(__file__).resolve().parent.parent.parent


def load_allowlist_roots() -> list[Path]:
    raw = os.environ.get("SEO_AGENT_REPO_ALLOWLIST", "sample-site").strip()
    if not raw:
        raw = "sample-site"
    roots: list[Path] = []
    base = _project_root()
    for part in raw.split(";"):
        p = (base / part.strip()).resolve() if not Path(part.strip()).is_absolute() else Path(part.strip()).resolve()
        roots.append(p)
    return roots


def assert_repo_allowed(repo_root: str | None) -> Path:
    if not repo_root or not str(repo_root).strip():
        raise ValueError("repo_root is required when applying fixes")
    candidate = Path(repo_root.strip())
    resolved = (candidate if candidate.is_absolute() else (_project_root() / candidate)).resolve()
    allow = load_allowlist_roots()
    for root in allow:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise PermissionError(f"repo_root not under allowlist: {resolved}")
