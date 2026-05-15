from app.agents.planner import build_plan
from app.orchestrator.context import AnalyzeRequest


def test_plan_includes_modify_when_apply():
    req = AnalyzeRequest(
        url="http://localhost:3000",
        apply_fixes=True,
        dry_run=False,
        repo_root="sample-site",
    )
    assert "code_modify" in build_plan(req)


def test_plan_includes_modify_when_apply_with_repo_url():
    req = AnalyzeRequest(
        url="http://localhost:3000",
        apply_fixes=True,
        dry_run=False,
        repo_url="https://github.com/example/repo.git",
        repo_root=None,
    )
    assert "code_modify" in build_plan(req)


def test_plan_skips_modify_when_dry_run():
    req = AnalyzeRequest(
        url="http://localhost:3000",
        apply_fixes=True,
        dry_run=True,
        repo_root="sample-site",
    )
    assert "code_modify" not in build_plan(req)
