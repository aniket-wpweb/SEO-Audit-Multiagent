"""Resolve CLI executables for subprocess (Windows-safe)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Sequence


def resolve_executable(name: str) -> str:
    """
    Return a path or name subprocess can execute.

    On Windows, ``npm`` / ``pnpm`` / ``yarn`` are often ``*.cmd`` shims;
    bare names fail with WinError 2 when ``shell=False``.
    """
    if os.path.isabs(name) and os.path.isfile(name):
        return name
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "win32":
        for ext in (".cmd", ".exe", ".bat"):
            found = shutil.which(name + ext)
            if found:
                return found
    return name


def run_cmd(
    argv: Sequence[str],
    *,
    cwd: str | None = None,
    capture_output: bool = True,
    text: bool = True,
    timeout: int | float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Like ``subprocess.run`` but resolves ``argv[0]`` on Windows."""
    if not argv:
        raise ValueError("argv must not be empty")
    parts = [resolve_executable(argv[0]), *list(argv[1:])]
    return subprocess.run(
        parts,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        check=check,
        shell=False,
    )
