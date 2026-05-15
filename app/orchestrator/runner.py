from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.orchestrator.context import RunContext, StepState
from app.orchestrator.registry import ToolRegistry
from app.services.git_repo import try_commit_automated_fixes, try_push_origin_test
from app.validators.post_exec import maybe_post_build
from app.validators.pre_exec import validate_pre_analyze


def build_registry() -> ToolRegistry:
    from app.tools import code_modify, crawl, detect_stack, format_results, seo_audit, sop_validate

    reg = ToolRegistry()
    reg.register("crawl", crawl.run)
    reg.register("detect_stack", detect_stack.run)
    reg.register("seo_audit", seo_audit.run)
    reg.register("sop_validate", sop_validate.run)
    reg.register("code_modify", code_modify.run)
    reg.register("format_results", format_results.run)
    return reg


def _maybe_git_commit_repo_url(ctx: RunContext, progress_sink: list[dict[str, Any]] | None) -> None:
    """After successful post_build, commit on ``test`` when apply used ``repo_url``."""
    if not (ctx.request.repo_url or "").strip():
        return
    if not ctx.repo_path or not ctx.modify or not ctx.modify.files_touched:
        return
    post = ctx.post_build
    if not post or not post.ok:
        return
    _emit_progress(progress_sink, "git_commit", "running")
    sha, err = try_commit_automated_fixes(ctx.repo_path)
    if err:
        ctx.modify.git_commit_error = err
        _emit_progress(progress_sink, "git_commit", "failed", message=err[:300])
    else:
        ctx.modify.git_commit_sha = sha
        _emit_progress(progress_sink, "git_commit", "done", message=sha or "no changes to commit")

    auto_push = os.environ.get("SEO_AGENT_GIT_AUTO_PUSH", "0").strip().lower() in ("1", "true", "yes")
    if auto_push and not err:
        _emit_progress(progress_sink, "git_push", "running")
        ok, push_err = try_push_origin_test(ctx.repo_path)
        if ok:
            ctx.modify.git_push_ok = True
            _emit_progress(progress_sink, "git_push", "done", message="origin test")
        else:
            ctx.modify.git_push_error = push_err
            _emit_progress(progress_sink, "git_push", "failed", message=(push_err or "")[:300])


def _emit_progress(
    sink: list[dict[str, Any]] | None,
    step: str,
    state: str,
    message: str | None = None,
) -> None:
    if sink is None:
        return
    row: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "step": step,
        "state": state,
    }
    if message:
        row["message"] = message
    sink.append(row)


def run_pipeline(
    ctx: RunContext,
    reg: ToolRegistry | None = None,
    *,
    progress_sink: list[dict[str, Any]] | None = None,
) -> RunContext:
    reg = reg or build_registry()
    _emit_progress(progress_sink, "pre_validation", "running")
    try:
        validate_pre_analyze(ctx)
    except Exception as e:
        _emit_progress(progress_sink, "pre_validation", "failed", message=str(e))
        ctx.fatal_error = {"error_code": "pre_validation", "message": str(e)}
        return ctx
    _emit_progress(progress_sink, "pre_validation", "done")

    from app.agents.planner import build_plan

    ctx.plan = build_plan(ctx.request)
    for step in ctx.plan:
        ctx.step_status[step] = StepState.pending

    for step in ctx.plan:
        if ctx.fatal_error:
            break
        ctx.step_status[step] = StepState.running
        _emit_progress(progress_sink, step, "running")
        try:
            fn = reg.get(step)
            fn(ctx)
        except Exception as e:
            ctx.step_status[step] = StepState.failed
            _emit_progress(progress_sink, step, "failed", message=str(e))
            ctx.fatal_error = {"error_code": f"tool_{step}", "message": str(e)}
            break
        ctx.step_status[step] = StepState.done
        _emit_progress(progress_sink, step, "done")

    _emit_progress(progress_sink, "post_build", "running")
    maybe_post_build(ctx)
    if ctx.post_build is not None:
        if ctx.post_build.ok:
            _emit_progress(progress_sink, "post_build", "done")
        else:
            tail = (ctx.post_build.log_tail or "")[:500]
            _emit_progress(progress_sink, "post_build", "failed", message=tail or "build failed")
    else:
        _emit_progress(progress_sink, "post_build", "skipped")

    _maybe_git_commit_repo_url(ctx, progress_sink)

    if ctx.formatted is not None:
        if ctx.post_build is not None:
            ctx.formatted.post_build = ctx.post_build
        if ctx.modify is not None:
            ctx.formatted.diffs = ctx.modify.diffs
            ctx.formatted.files_touched = ctx.modify.files_touched
            ctx.formatted.backups = ctx.modify.backups
            if (ctx.request.repo_url or "").strip():
                git = dict(ctx.formatted.git)
                git.setdefault("branch", "test")
                if ctx.modify.git_commit_sha:
                    git["commit"] = ctx.modify.git_commit_sha
                if ctx.modify.git_commit_error:
                    git["commit_error"] = ctx.modify.git_commit_error
                if ctx.modify.git_push_ok:
                    git["push"] = "origin test"
                if ctx.modify.git_push_error:
                    git["push_error"] = ctx.modify.git_push_error
                ctx.formatted = ctx.formatted.model_copy(update={"git": git})
    return ctx
