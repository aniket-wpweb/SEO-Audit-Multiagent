"""Post-build after seo_fix; rollback on failure."""

from __future__ import annotations

import os
from pathlib import Path

from app.orchestrator.context import PostBuild, RunContext
from app.services.backup import restore_mappings
from app.services.repo_stack import RepoStackInfo, detect_repo_stack
from app.services.subprocess_cmd import run_cmd


def _build_command(repo_stack: RepoStackInfo) -> list[str] | None:
    if not repo_stack.is_node_project or not repo_stack.has_build_script:
        return None
    pm = repo_stack.package_manager
    if pm == "pnpm":
        return ["pnpm", "run", "build"]
    if pm == "yarn":
        return ["yarn", "run", "build"]
    return ["npm", "run", "build"]


def maybe_post_build(ctx: RunContext) -> None:
    if not ctx.modify or not ctx.modify.files_touched:
        ctx.post_build = PostBuild(ok=True, log_tail="")
        return
    if not ctx.repo_path:
        ctx.post_build = PostBuild(ok=False, log_tail="missing repo_path")
        return

    repo = Path(ctx.repo_path)
    stack = ctx.repo_stack if ctx.repo_stack is not None else detect_repo_stack(repo)
    ctx.repo_stack = stack
    cmd = _build_command(stack)
    if cmd is None:
        ctx.post_build = PostBuild(ok=True, log_tail="skipped: no Node build script in repo")
        return

    skip = os.environ.get("SEO_AGENT_SKIP_POST_BUILD", "").strip().lower() in ("1", "true", "yes")
    if skip:
        ctx.post_build = PostBuild(ok=True, log_tail="skipped: SEO_AGENT_SKIP_POST_BUILD=1")
        return

    install_tail = ""
    if stack.is_node_project and not (repo / "node_modules").is_dir():
        pm = stack.package_manager
        if pm == "pnpm":
            install_cmd = ["pnpm", "install"]
        elif pm == "yarn":
            install_cmd = ["yarn", "install"]
        else:
            install_cmd = ["npm", "ci"] if (repo / "package-lock.json").is_file() else ["npm", "install"]
        try:
            inst = run_cmd(install_cmd, cwd=str(repo), timeout=900)
            install_tail = (inst.stdout or "")[-2000:] + "\n" + (inst.stderr or "")[-2000:]
            if inst.returncode != 0:
                ctx.post_build = PostBuild(
                    ok=False,
                    log_tail=f"dependency install failed ({install_cmd[0]}):\n{install_tail[-4000:]}",
                )
                return
        except FileNotFoundError as exc:
            ctx.post_build = PostBuild(
                ok=False,
                log_tail=f"dependency install not found ({install_cmd[0]}): {exc}",
            )
            return

    try:
        proc = run_cmd(cmd, cwd=str(repo), timeout=600)
    except FileNotFoundError as exc:
        ctx.post_build = PostBuild(
            ok=False,
            log_tail=f"build command not found ({cmd[0]}): {exc}. Install Node.js or add it to PATH.",
        )
        return
    tail = (proc.stdout or "")[-4000:] + "\n" + (proc.stderr or "")[-4000:]
    if proc.returncode != 0:
        mappings: list[tuple[Path, Path]] = []
        for i, touched in enumerate(ctx.modify.files_touched):
            orig = repo / touched.replace("/", os.sep)
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
