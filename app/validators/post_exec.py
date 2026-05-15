"""Post-build after code_modify; rollback on failure."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.orchestrator.context import ModifyResult, PostBuild, RunContext
from app.services.backup import restore_mappings


def maybe_post_build(ctx: RunContext) -> None:
    if not ctx.modify or not ctx.modify.files_touched:
        ctx.post_build = PostBuild(ok=True, log_tail="")
        return
    if not ctx.repo_path:
        ctx.post_build = PostBuild(ok=False, log_tail="missing repo_path")
        return
    repo = Path(ctx.repo_path)
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=600,
        shell=False,
    )
    tail = (proc.stdout or "")[-4000:] + "\n" + (proc.stderr or "")[-4000:]
    if proc.returncode != 0:
        mappings: list[tuple[Path, Path]] = []
        for i, touched in enumerate(ctx.modify.files_touched):
            orig = repo / touched
            if i < len(ctx.modify.backups):
                mappings.append((orig, Path(ctx.modify.backups[i])))
        try:
            restore_mappings(mappings)
        except Exception as exc:
            tail += f"\n[rollback_error] {exc}"
        ctx.post_build = PostBuild(ok=False, log_tail=tail)
        ctx.modify.diffs = []
        ctx.modify.files_touched = []
        return
    ctx.post_build = PostBuild(ok=True, log_tail=tail[-2000:])
