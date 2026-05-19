from __future__ import annotations

import sys

from app.services.subprocess_cmd import resolve_executable


def test_resolve_executable_git() -> None:
    path = resolve_executable("git")
    assert path
    if sys.platform == "win32":
        assert path.lower().endswith((".exe", ".cmd")) or "git" in path.lower()


def test_resolve_executable_npm_on_windows() -> None:
    path = resolve_executable("npm")
    assert path
    if sys.platform == "win32":
        assert path.lower().endswith(".cmd") or path.lower().endswith(".exe")
