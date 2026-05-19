from app.agents.planner import build_plan
from app.orchestrator.context import AnalyzeRequest


def test_plan_includes_seo_fix_when_apply_with_repo_url():
    req = AnalyzeRequest(
        url="http://localhost:3000",
        apply_fixes=True,
        dry_run=False,
        repo_url="https://github.com/example/repo.git",
    )
    plan = build_plan(req)
    assert "seo_fix" in plan
    assert "code_modify" not in plan


def test_plan_skips_seo_fix_when_dry_run():
    req = AnalyzeRequest(
        url="http://localhost:3000",
        apply_fixes=True,
        dry_run=True,
        repo_url="https://github.com/example/repo.git",
    )
    assert "seo_fix" not in build_plan(req)


def test_plan_skips_seo_fix_without_repo_url():
    req = AnalyzeRequest(url="http://localhost:3000", apply_fixes=True, dry_run=False)
    assert "seo_fix" not in build_plan(req)
