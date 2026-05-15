"""pre_analyze validation rules."""

from __future__ import annotations

import pytest

from app.orchestrator.context import AnalyzeRequest, RunContext
from app.validators.pre_exec import validate_pre_analyze


def test_rejects_both_repo_root_and_repo_url() -> None:
    ctx = RunContext(
        request=AnalyzeRequest(
            url="http://example.com",
            apply_fixes=True,
            dry_run=False,
            repo_root="sample-site",
            repo_url="https://github.com/a/b.git",
        ),
    )
    with pytest.raises(ValueError, match="only one"):
        validate_pre_analyze(ctx)


def test_rejects_neither_repo_target_when_apply() -> None:
    ctx = RunContext(
        request=AnalyzeRequest(
            url="http://example.com",
            apply_fixes=True,
            dry_run=False,
            repo_root=None,
            repo_url=None,
        ),
    )
    with pytest.raises(ValueError, match="repo_root or repo_url"):
        validate_pre_analyze(ctx)
