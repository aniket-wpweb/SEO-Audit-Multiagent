import pytest

from app.orchestrator.context import AnalyzeRequest, RunContext


def test_requires_repo_url_when_apply():
    ctx = RunContext(
        request=AnalyzeRequest(
            url="http://example.com",
            apply_fixes=True,
            dry_run=False,
            repo_url=None,
        ),
    )
    from app.validators.pre_exec import validate_pre_analyze

    with pytest.raises(ValueError, match="repo_url is required"):
        validate_pre_analyze(ctx)
