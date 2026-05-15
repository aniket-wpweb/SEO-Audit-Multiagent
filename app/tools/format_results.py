from __future__ import annotations

from typing import Any

from app.orchestrator.context import FormattedResults, ModifyResult, PostBuild, RunContext


def run(ctx: RunContext) -> None:
    stack = ctx.stack.model_dump() if ctx.stack else {}
    issues = [i.model_dump() for i in ctx.issues]
    sop: list[dict] = []
    for i, row in enumerate(ctx.sop_rows):
        d = row.model_dump()
        if i < len(ctx.issues):
            d["issue"] = ctx.issues[i].model_dump()
        sop.append(d)
    modify = ctx.modify or ModifyResult()
    post = ctx.post_build or PostBuild(ok=True, log_tail="")
    git: dict[str, Any] = {}
    if (ctx.request.repo_url or "").strip():
        git["branch"] = "test"
        if modify.git_commit_sha:
            git["commit"] = modify.git_commit_sha
        if modify.git_commit_error:
            git["commit_error"] = modify.git_commit_error
        if modify.git_push_ok:
            git["push"] = "origin test"
        if modify.git_push_error:
            git["push_error"] = modify.git_push_error
    ctx.formatted = FormattedResults(
        stack=stack,
        issues=issues,
        sop=sop,
        diffs=modify.diffs,
        files_touched=modify.files_touched,
        backups=modify.backups,
        post_build=post,
        git=git,
    )
