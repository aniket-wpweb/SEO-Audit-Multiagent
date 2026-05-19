"""seo_fix with mocked FixProvider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.orchestrator.context import AnalyzeRequest, Issue, RunContext
from app.services.fix_provider.base import FixFileResult
from app.services.repo_stack import RepoStackInfo
from app.tools import seo_fix


class _MockProvider:
    name = "mock"

    def fix_file(self, **kwargs) -> FixFileResult:
        c = kwargs["content"]
        if "PATCH" not in c:
            return FixFileResult(content=c + "\n// PATCH\n", provider="mock")
        return FixFileResult(content=None, reason="unchanged", provider="mock")


def test_seo_fix_writes_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    page = repo / "app" / "page.tsx"
    page.write_text("export default function P() { return <h1>x</h1>; }", encoding="utf-8")

    ctx = RunContext(
        request=AnalyzeRequest(
            url="http://example.com",
            apply_fixes=True,
            dry_run=False,
            repo_url="https://github.com/x/y.git",
        ),
        repo_path=repo,
        issues=[
            Issue(
                issue_id="1",
                rule_id="duplicate_h1",
                severity="medium",
                page_url="http://example.com",
                evidence="",
                suggested_fix="",
                file_hint="app/page.tsx",
            )
        ],
    )

    stack = RepoStackInfo(
        framework="nextjs_app",
        package_manager="npm",
        has_build_script=True,
        build_script="next build",
        source_roots=["app"],
        is_node_project=True,
    )

    with patch("app.tools.seo_fix.get_fix_provider", return_value=_MockProvider()):
        with patch("app.tools.seo_fix.build_fix_targets") as bft:
            from app.services.issue_file_mapper import FixTarget

            bft.return_value = [FixTarget(rel_path="app/page.tsx", issues=ctx.issues)]
            with patch("app.tools.seo_fix.detect_repo_stack", return_value=stack):
                seo_fix.run(ctx)

    assert ctx.modify is not None
    assert "app/page.tsx" in ctx.modify.files_touched
    assert ctx.modify.fix_provider_used == "mock"
    assert "PATCH" in page.read_text(encoding="utf-8")
