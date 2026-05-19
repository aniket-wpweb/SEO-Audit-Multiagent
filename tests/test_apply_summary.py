"""Tests for apply_summary and post-apply pipeline helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.planner import build_plan
from app.orchestrator.context import AnalyzeRequest, Issue, ModifyResult, RunContext, StackInfo
from app.tools.format_results import compute_apply_summary, run as format_results_run
from app.tools.llm_apply_review import run as llm_apply_review_run


def test_plan_includes_seo_fix():
    req = AnalyzeRequest(
        url="http://localhost:3000",
        apply_fixes=True,
        dry_run=False,
        repo_url="https://github.com/example/repo.git",
    )
    plan = build_plan(req)
    assert "seo_fix" in plan
    assert plan[-1] == "seo_fix"


def test_compute_apply_summary_audit_only_with_issues():
    ctx = RunContext(
        request=AnalyzeRequest(url="http://x", apply_fixes=False),
        issues=[
            Issue(
                issue_id="1",
                rule_id="missing_alt",
                severity="medium",
                page_url="http://x",
                evidence="img",
                suggested_fix="alt",
                file_hint="app/page.tsx",
            )
        ],
    )
    s = compute_apply_summary(ctx)
    assert s["pre_fix_issue_count"] == 1
    assert s["apply_attempted"] is False
    assert "Audit-only" in s["human_note"]


def test_compute_apply_summary_no_diffs_but_issues_apply_attempted(tmp_path: Path):
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "app").mkdir()
    ctx = RunContext(
        request=AnalyzeRequest(
            url="http://x",
            apply_fixes=True,
            dry_run=False,
            repo_url="https://github.com/a/b.git",
        ),
        repo_path=repo,
        issues=[
            Issue(
                issue_id="1",
                rule_id="missing_alt",
                severity="medium",
                page_url="http://x",
                evidence="img",
                suggested_fix="alt",
                file_hint=None,
            )
        ],
        modify=ModifyResult(diffs=[], files_touched=[], backups=[], fix_provider_used="chain"),
        stack=StackInfo(label="nextjs", confidence="high"),
    )
    s = compute_apply_summary(ctx)
    assert s["apply_attempted"] is True
    assert "crawled URL" in s["human_note"]


def test_format_results_includes_apply_summary_and_skipped_reason():
    ctx = RunContext(
        request=AnalyzeRequest(
            url="http://x",
            apply_fixes=True,
            dry_run=True,
            repo_url="https://github.com/a/b.git",
        ),
        issues=[],
        modify=ModifyResult(skipped_reason="dry_run_or_apply_off"),
        stack=StackInfo(label="nextjs", confidence="high"),
        sop_rows=[],
        post_build=None,
    )
    format_results_run(ctx)
    assert ctx.formatted is not None
    assert ctx.formatted.apply_summary["skipped_reason"] == "dry_run_or_apply_off"


def test_llm_apply_review_skipped_when_sop_rules_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOP_RULES_ONLY", "1")
    ctx = RunContext(
        request=AnalyzeRequest(
            url="http://x",
            apply_fixes=True,
            dry_run=False,
            repo_url="https://github.com/a/b.git",
            llm_apply_review=True,
        ),
        modify=ModifyResult(),
        post_build=None,
    )
    llm_apply_review_run(ctx)
    assert ctx.llm_apply_review is not None
    assert ctx.llm_apply_review.get("status") == "skipped"
