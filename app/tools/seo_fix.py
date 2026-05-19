"""Apply SEO fixes to cloned repository files via pluggable FixProvider."""

from __future__ import annotations

import difflib
from pathlib import Path

from app.orchestrator.context import ModifyResult, RunContext
from app.services.backup import backup_file
from app.services.fix_provider import get_fix_provider
from app.services.issue_file_mapper import build_fix_targets
from app.services.repo_layout import join_posix_rel
from app.services.repo_stack import detect_repo_stack

ALLOWED_SUFFIXES = (".tsx", ".ts", ".jsx", ".js", ".html", ".vue", ".mdx")


def _unified_diff(rel_path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
    )


def _allowed_path(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    if ".." in rel.split("/"):
        return False
    return rel.endswith(ALLOWED_SUFFIXES)


def run(ctx: RunContext) -> None:
    req = ctx.request
    if req.dry_run or not req.apply_fixes:
        ctx.modify = ModifyResult(skipped_reason="dry_run_or_apply_off")
        return
    repo = ctx.repo_path
    if repo is None:
        ctx.modify = ModifyResult(skipped_reason="no_repo_path")
        return

    ctx.repo_stack = detect_repo_stack(repo)
    provider = get_fix_provider(req.url)
    targets = build_fix_targets(ctx, ctx.repo_stack)

    diffs: list[str] = []
    touched: list[str] = []
    backups: list[str] = []
    fix_errors: list[dict[str, str]] = []
    backup_root = repo / ".seo-agent-backups" / ctx.run_id

    for target in targets:
        rel = target.rel_path
        if not _allowed_path(rel):
            fix_errors.append({"file": rel, "reason": "extension_not_allowed"})
            continue
        path = join_posix_rel(repo, rel)
        if not path.is_file():
            fix_errors.append({"file": rel, "reason": "missing_on_disk"})
            continue
        before = path.read_text(encoding="utf-8")
        result = provider.fix_file(
            rel_path=rel,
            content=before,
            issues=target.issues,
            repo_stack=ctx.repo_stack,
            site_url=req.url,
        )
        if result.content is None:
            if result.reason not in ("no_rule_match", "unchanged", "SEO_FIX_API_KEY not set"):
                fix_errors.append({"file": rel, "reason": result.reason})
            continue
        after = result.content
        if after == before:
            continue
        bpath = backup_file(repo, path, backup_root)
        path.write_text(after, encoding="utf-8")
        rel_touch = str(path.relative_to(repo)).replace("\\", "/")
        touched.append(rel_touch)
        backups.append(str(bpath))
        diff = _unified_diff(rel_touch, before, after)
        if diff.strip():
            diffs.append(diff)

    ctx.apply_counters = {
        "fix_targets": len(targets),
        "fix_errors_count": len(fix_errors),
        "fix_plan_paths": [t.rel_path for t in targets[:30]],
    }
    ctx.modify = ModifyResult(
        diffs=diffs,
        files_touched=touched,
        backups=backups,
        fix_provider_used=provider.name,
        fix_errors=fix_errors,
    )
