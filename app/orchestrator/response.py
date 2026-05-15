"""Shared HTTP payload shape for /analyze and async job results."""

from __future__ import annotations

from typing import Any

from app.orchestrator.context import RunContext


def analyze_result_dict(ctx: RunContext) -> tuple[int, dict[str, Any]]:
    """Return (http_status, json_body) matching synchronous POST /analyze."""
    plan_out = [{"id": s, "status": str(ctx.step_status.get(s, ""))} for s in ctx.plan]
    results_dump = ctx.formatted.model_dump(mode="json") if ctx.formatted else {}
    if ctx.fatal_error:
        return (
            400,
            {
                "status": "failed",
                "plan": plan_out,
                "error": ctx.fatal_error,
                "results": results_dump,
            },
        )
    post = ctx.post_build
    if post and not post.ok:
        return (
            500,
            {
                "status": "failed",
                "plan": plan_out,
                "results": results_dump,
            },
        )
    return (
        200,
        {
            "status": "completed",
            "plan": plan_out,
            "results": results_dump,
        },
    )
