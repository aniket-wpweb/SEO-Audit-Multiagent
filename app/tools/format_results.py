from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

from app.orchestrator.context import FormattedResults, ModifyResult, PostBuild, RunContext
from app.services.repo_layout import join_posix_rel


def _auto_fix_rule_ids() -> set[str]:
    out = {"missing_meta", "duplicate_h1", "missing_alt"}
    if os.environ.get("SEO_AGENT_FIX_BROKEN_LINKS", "").strip().lower() in ("1", "true", "yes"):
        out.add("broken_link")
    return out


def compute_apply_summary(ctx: RunContext) -> dict[str, Any]:
    modify = ctx.modify or ModifyResult()
    issues = ctx.issues
    n_issues = len(issues)
    rule_counts = dict(Counter(i.rule_id for i in issues))
    missing_hint = [i for i in issues if not i.file_hint]
    nh_count = len(missing_hint)
    nh_ids = [i.issue_id for i in missing_hint[:25]]

    hint_missing_on_disk = 0
    repo = ctx.repo_path
    if repo is not None:
        root = Path(repo)
        seen: set[str] = set()
        for i in issues:
            if not i.file_hint:
                continue
            rel = i.file_hint.replace("\\", "/")
            if rel in seen:
                continue
            seen.add(rel)
            if not join_posix_rel(root, rel).is_file():
                hint_missing_on_disk += 1

    supported = _auto_fix_rule_ids()
    not_auto_set: set[str] = set()
    for i in issues:
        if i.rule_id not in supported:
            not_auto_set.add(i.rule_id)
        elif not i.file_hint:
            not_auto_set.add(i.rule_id)
    not_auto_unique = sorted(not_auto_set)[:20]

    counters = dict(ctx.apply_counters) if ctx.apply_counters else {}

    apply_attempted = (
        ctx.request.apply_fixes
        and not ctx.request.dry_run
        and bool((ctx.request.repo_url or "").strip())
    )

    parts: list[str] = []
    if modify.skipped_reason:
        parts.append(f"SEO fix step was skipped ({modify.skipped_reason}).")
    elif not apply_attempted:
        if n_issues == 0:
            parts.append("The audit reported no issues.")
        else:
            parts.append("Audit-only run; use Step 2 with a repository to apply fixes.")
    elif n_issues == 0:
        parts.append("Apply ran; the audit reported no issues for this crawl.")
    elif not modify.diffs and not modify.files_touched:
        parts.append(
            "The SEO table lists findings from the crawled URL; code changes apply only to the cloned repository.",
        )
        fix_target_count = int(counters.get("fix_targets") or 0)
        if fix_target_count > 0:
            parts.append(
                f"Issues were mapped to {fix_target_count} source file(s) but no patches were applied; "
                "check components imported via @/ aliases or image paths in evidence.",
            )
        if nh_count:
            parts.append(f"{nh_count} issue(s) have no mapped source file in the clone.")
        if hint_missing_on_disk:
            parts.append(
                f"{hint_missing_on_disk} distinct file_hint path(s) from the audit do not exist in this checkout.",
            )
        if not_auto_unique:
            parts.append(
                "Some rules are audit-only or need extra configuration (e.g. broken_link may require SEO_AGENT_FIX_BROKEN_LINKS=1).",
            )
        parts.append(
            "If the running site at the crawl URL is not built from this branch, redeploy or run the site from the clone before expecting the audit to clear.",
        )
    else:
        parts.append("Edits were applied to the clone; re-run the crawl after redeploy to confirm the live site.")

    human = " ".join(parts).strip()
    if ctx.reaudit_error:
        suffix = f"Re-audit failed: {ctx.reaudit_error}"
        human = f"{human} {suffix}" if human else suffix

    return {
        "skipped_reason": modify.skipped_reason,
        "pre_fix_issue_count": n_issues,
        "rule_counts": rule_counts,
        "issues_missing_file_hint": nh_count,
        "issues_missing_file_hint_ids": nh_ids,
        "hint_paths_missing_on_disk": hint_missing_on_disk,
        "files_touched_count": len(modify.files_touched),
        "diffs_count": len(modify.diffs),
        "auto_fix_rules_supported": sorted(supported),
        "issues_not_auto_fixed_rule_ids": not_auto_unique,
        "apply_counters": counters,
        "fix_plan": list(ctx.fix_plan)[:50],
        "fix_provider_used": modify.fix_provider_used,
        "fix_errors": modify.fix_errors[:30],
        "git_branch": ctx.git_branch,
        "human_note": human,
        "reaudit_ran": ctx.reaudit_ran,
        "reaudit_error": ctx.reaudit_error,
        "reaudit_note": (
            "Second crawl finished; see issues_after_apply. If the URL still serves an old build, counts may be unchanged until you redeploy."
            if ctx.reaudit_ran
            else ""
        ),
        "apply_attempted": apply_attempted,
    }


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
        git["branch"] = ctx.git_branch or "seo-fixes"
        if modify.git_commit_sha:
            git["commit"] = modify.git_commit_sha
        if modify.git_commit_error:
            git["commit_error"] = modify.git_commit_error
        if modify.git_push_ok:
            git["push"] = "origin test"
        if modify.git_push_error:
            git["push_error"] = modify.git_push_error

    apply_summary = compute_apply_summary(ctx)
    issues_after: list[dict[str, Any]] | None = None
    if ctx.reaudit_ran:
        issues_after = [i.model_dump() for i in ctx.issues_after_apply]

    ctx.formatted = FormattedResults(
        stack=stack,
        issues=issues,
        sop=sop,
        diffs=modify.diffs,
        files_touched=modify.files_touched,
        backups=modify.backups,
        post_build=post,
        git=git,
        apply_summary=apply_summary,
        issues_after_apply=issues_after,
        llm_apply_review=ctx.llm_apply_review,
    )
