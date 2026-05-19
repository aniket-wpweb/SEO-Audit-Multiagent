"""Post-apply LLM review (Ollama JSON); optional, gated by request or env."""

from __future__ import annotations

import json
import os

from app.orchestrator.context import ModifyResult, RunContext
from app.services.llm_provider import LLMProvider


def run(ctx: RunContext) -> None:
    want = ctx.request.llm_apply_review or os.environ.get("SEO_AGENT_LLM_APPLY_REVIEW", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not want:
        return
    if not ctx.request.apply_fixes or ctx.request.dry_run:
        return

    if os.environ.get("SOP_RULES_ONLY", "0") == "1":
        ctx.llm_apply_review = {
            "status": "skipped",
            "reason": "SOP_RULES_ONLY=1",
            "remaining_concerns": [],
            "next_actions": [],
            "needs_redeploy": True,
        }
        return

    llm = LLMProvider()
    modify = ctx.modify or ModifyResult()
    pre_n = len(ctx.issues)
    post_n = len(ctx.issues_after_apply) if ctx.reaudit_ran else None
    touched = list(modify.files_touched)
    diff_n = len(modify.diffs)

    payload = {
        "crawled_url": ctx.request.url,
        "pre_fix_issue_count": pre_n,
        "issues_after_apply_count": post_n,
        "files_touched": touched[:40],
        "diff_count": diff_n,
        "post_build_ok": ctx.post_build.ok if ctx.post_build else None,
        "reaudit_ran": ctx.reaudit_ran,
    }
    system = (
        "You are an SEO release assistant. Reply with JSON only, no markdown. "
        "Schema: {status: string (ok|warning|blocked), remaining_concerns: string[], "
        "next_actions: string[], needs_redeploy: boolean}. "
        "The pre-fix issue count is from a crawl of crawled_url before local repo edits; "
        "issues_after_apply_count is from a second crawl only if reaudit_ran is true. "
        "If the user did not redeploy the crawled app from the patched repo, needs_redeploy should be true."
    )
    user = json.dumps(payload, indent=2)
    parsed = llm.ollama_json_chat(system=system, user=user, timeout=90.0)
    if parsed and isinstance(parsed, dict):
        ctx.llm_apply_review = {
            "status": str(parsed.get("status", "warning")),
            "remaining_concerns": list(parsed.get("remaining_concerns") or []),
            "next_actions": list(parsed.get("next_actions") or []),
            "needs_redeploy": bool(parsed.get("needs_redeploy", True)),
        }
    else:
        ctx.llm_apply_review = {
            "status": "unavailable",
            "reason": "ollama_unreachable_or_invalid_json",
            "remaining_concerns": [],
            "next_actions": ["Check OLLAMA_HOST / OLLAMA_MODEL or set SOP_RULES_ONLY=1 to skip LLM."],
            "needs_redeploy": True,
        }
