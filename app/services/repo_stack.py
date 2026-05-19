"""Detect project stack from a cloned repository filesystem."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RepoStackInfo:
    framework: str  # nextjs_app | nextjs_pages | static | unknown
    package_manager: str  # npm | pnpm | yarn | none
    has_build_script: bool
    build_script: str | None
    source_roots: list[str] = field(default_factory=list)
    is_node_project: bool = False


def _read_package_json(repo: Path) -> dict | None:
    pkg = repo / "package.json"
    if not pkg.is_file():
        return None
    try:
        return json.loads(pkg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def detect_repo_stack(repo: Path) -> RepoStackInfo:
    root = repo.resolve()
    pkg = _read_package_json(root)
    roots: list[str] = []
    for rel in ("app", "src/app", "pages", "src/pages", "src", "public"):
        p = root.joinpath(*rel.split("/"))
        if p.is_dir():
            roots.append(rel)

    framework = "unknown"
    if (root / "app").is_dir() or (root / "src" / "app").is_dir():
        framework = "nextjs_app"
    elif (root / "pages").is_dir() or (root / "src" / "pages").is_dir():
        framework = "nextjs_pages"
    elif any((root / r).rglob("*.html") for r in (".", "public") if (root / r).exists()):
        framework = "static"

    pm = "none"
    if (root / "pnpm-lock.yaml").is_file():
        pm = "pnpm"
    elif (root / "yarn.lock").is_file():
        pm = "yarn"
    elif (root / "package-lock.json").is_file() or pkg:
        pm = "npm"

    scripts = (pkg or {}).get("scripts") or {}
    build_script = scripts.get("build")
    has_build = bool(build_script)
    is_node = pkg is not None

    return RepoStackInfo(
        framework=framework,
        package_manager=pm,
        has_build_script=has_build,
        build_script=str(build_script) if build_script else None,
        source_roots=roots or ["."],
        is_node_project=is_node,
    )
