from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class StepState(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class AnalyzeRequest(BaseModel):
    url: str
    depth: int = 2
    max_pages: int = 10
    dry_run: bool = False
    apply_fixes: bool = False
    reaudit_after_apply: bool = Field(
        default=False,
        description="After post_build, re-run crawl+seo_audit against the same URL; results in issues_after_apply.",
    )
    llm_apply_review: bool = Field(
        default=False,
        description="Run Ollama JSON review after apply (or set SEO_AGENT_LLM_APPLY_REVIEW=1).",
    )
    git_branch: str | None = Field(
        default=None,
        description="Branch to checkout/create after clone; default from SEO_AGENT_GIT_BRANCH or seo-fixes.",
    )
    repo_url: str | None = Field(
        default=None,
        description="HTTPS/SSH Git remote; clone under SEO_AGENT_CLONE_ROOT/<run_id>.",
    )


class PageRecord(BaseModel):
    url: str
    status_code: int
    html: str = Field(repr=False)


class StackInfo(BaseModel):
    label: str
    confidence: str  # low | medium | high


class Issue(BaseModel):
    issue_id: str
    rule_id: str
    severity: str
    page_url: str
    evidence: str
    suggested_fix: str
    file_hint: str | None = None


class SopRow(BaseModel):
    issue_id: str
    sop_status: str
    sop_reference: str
    sop_snippet: str = ""


class ModifyResult(BaseModel):
    diffs: list[str] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)
    backups: list[str] = Field(default_factory=list)
    skipped_reason: str | None = None
    fix_provider_used: str | None = None
    fix_errors: list[dict[str, str]] = Field(default_factory=list)
    git_commit_sha: str | None = None
    git_commit_error: str | None = None
    git_push_ok: bool = False
    git_push_error: str | None = None


class PostBuild(BaseModel):
    ok: bool
    log_tail: str = ""


class FormattedResults(BaseModel):
    stack: dict[str, Any]
    issues: list[dict[str, Any]]
    sop: list[dict[str, Any]]
    diffs: list[str]
    files_touched: list[str]
    backups: list[str]
    post_build: PostBuild
    git: dict[str, Any] = Field(default_factory=dict)
    apply_summary: dict[str, Any] = Field(default_factory=dict)
    issues_after_apply: list[dict[str, Any]] | None = None
    llm_apply_review: dict[str, Any] | None = None


class RunContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    request: AnalyzeRequest
    repo_path: Path | None = None
    git_branch: str | None = None
    repo_stack: Any = None
    fix_plan: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    step_status: dict[str, StepState] = Field(default_factory=dict)
    pages: list[PageRecord] = Field(default_factory=list)
    stack: StackInfo | None = None
    issues: list[Issue] = Field(default_factory=list)
    issues_after_apply: list[Issue] = Field(default_factory=list)
    reaudit_ran: bool = False
    reaudit_error: str | None = None
    sop_rows: list[SopRow] = Field(default_factory=list)
    modify: ModifyResult | None = None
    apply_counters: dict[str, Any] = Field(default_factory=dict)
    llm_apply_review: dict[str, Any] | None = None
    formatted: FormattedResults | None = None
    post_build: PostBuild | None = None
    fatal_error: dict[str, Any] | None = None
