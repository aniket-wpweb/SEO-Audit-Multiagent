from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.orchestrator.context import RunContext, StepState
from app.orchestrator.registry import ToolRegistry
from app.services.git_repo import (
    default_git_branch,
    try_commit_automated_fixes,
    try_push_origin_branch,
)
from app.validators.post_exec import maybe_post_build
from app.validators.pre_exec import validate_pre_analyze


def build_registry() -> ToolRegistry:
    from app.tools import crawl, detect_stack, format_results, seo_audit, seo_fix, sop_validate

    reg = ToolRegistry()
    reg.register("crawl", crawl.run)
    reg.register("detect_stack", detect_stack.run)
    reg.register("seo_audit", seo_audit.run)
    reg.register("sop_validate", sop_validate.run)
    reg.register("seo_fix", seo_fix.run)
    reg.register("format_results", format_results.run)
    return reg


def _maybe_git_commit_repo_url(ctx: RunContext, progress_sink: list[dict[str, Any]] | None) -> None:
    """After successful post_build, commit when apply used ``repo_url``."""
    if not (ctx.request.repo_url or "").strip():
        return
    if not ctx.repo_path or not ctx.modify or not ctx.modify.files_touched:
        return
    post = ctx.post_build
    if not post or not post.ok:
        return
    branch = ctx.git_branch or default_git_branch(ctx.request.git_branch)
    _emit_progress(progress_sink, "git_commit", "running")
    sha, err = try_commit_automated_fixes(ctx.repo_path, branch)
    if err:
        ctx.modify.git_commit_error = err
        _emit_progress(progress_sink, "git_commit", "failed", message=err[:300])
    else:
        ctx.modify.git_commit_sha = sha
        _emit_progress(progress_sink, "git_commit", "done", message=sha or "no changes to commit")

    auto_push = os.environ.get("SEO_AGENT_GIT_AUTO_PUSH", "0").strip().lower() in ("1", "true", "yes")
    if auto_push and not err:
        _emit_progress(progress_sink, "git_push", "running")
        ok, push_err = try_push_origin_branch(ctx.repo_path, branch)
        if ok:
            ctx.modify.git_push_ok = True
            _emit_progress(progress_sink, "git_push", "done", message=f"origin {branch}")
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


def _maybe_reaudit_after_apply(
    ctx: RunContext,
    reg: ToolRegistry,
    progress_sink: list[dict[str, Any]] | None,
) -> None:
    if ctx.fatal_error:
        return
    req = ctx.request
    want = req.reaudit_after_apply or os.environ.get("SEO_AGENT_REAUDIT_AFTER_APPLY", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not want:
        return
    if not req.apply_fixes or req.dry_run:
        return
    post = ctx.post_build
    if not post or not post.ok:
        return

    pre_pages = [p.model_copy() for p in ctx.pages]
    pre_issues = [i.model_copy() for i in ctx.issues]
    try:
        _emit_progress(progress_sink, "reaudit_crawl", "running")
        reg.get("crawl")(ctx)
        _emit_progress(progress_sink, "reaudit_crawl", "done")
        _emit_progress(progress_sink, "reaudit_detect_stack", "running")
        reg.get("detect_stack")(ctx)
        _emit_progress(progress_sink, "reaudit_detect_stack", "done")
        _emit_progress(progress_sink, "reaudit_seo_audit", "running")
        reg.get("seo_audit")(ctx)
        _emit_progress(progress_sink, "reaudit_seo_audit", "done")
    except Exception as e:
        ctx.pages = pre_pages
        ctx.issues = pre_issues
        ctx.reaudit_error = str(e)
        ctx.reaudit_ran = False
        ctx.issues_after_apply = []
        _emit_progress(progress_sink, "reaudit_seo_audit", "failed", message=str(e)[:500])
        return

    ctx.issues_after_apply = [i.model_copy() for i in ctx.issues]
    ctx.issues = pre_issues
    ctx.pages = pre_pages
    ctx.reaudit_ran = True


def _maybe_llm_apply_review(ctx: RunContext, progress_sink: list[dict[str, Any]] | None) -> None:
    if ctx.fatal_error:
        return
    want = ctx.request.llm_apply_review or os.environ.get("SEO_AGENT_LLM_APPLY_REVIEW", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not want:
        return
    if not ctx.request.apply_fixes or ctx.request.dry_run:
        return

    from app.tools import llm_apply_review

    _emit_progress(progress_sink, "llm_apply_review", "running")
    try:
        llm_apply_review.run(ctx)
    except Exception as e:
        ctx.llm_apply_review = {
            "status": "error",
            "reason": str(e)[:500],
            "remaining_concerns": [],
            "next_actions": [],
            "needs_redeploy": True,
        }
        _emit_progress(progress_sink, "llm_apply_review", "failed", message=str(e)[:300])
        return
    _emit_progress(progress_sink, "llm_apply_review", "done")


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

    _maybe_reaudit_after_apply(ctx, reg, progress_sink)
    _maybe_llm_apply_review(ctx, progress_sink)

    reg.get("format_results")(ctx)

    return ctx
