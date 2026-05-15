"""Backup and restore files for code_modify."""

from __future__ import annotations

import shutil
from pathlib import Path


def backup_file(repo_root: Path, src: Path, backup_root: Path) -> Path:
    """Copy src to backup_root preserving path relative to repo_root."""
    rel = src.relative_to(repo_root)
    dest = backup_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def restore_mappings(mappings: list[tuple[Path, Path]]) -> None:
    """Restore each original from its backup copy."""
    for original, backup_copy in mappings:
        shutil.copy2(backup_copy, original)
