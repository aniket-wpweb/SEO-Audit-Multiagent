from app.services.fix_provider.rules import RulesProvider
from app.orchestrator.context import Issue
from app.services.repo_stack import RepoStackInfo


def test_rules_provider_duplicate_h1():
    p = RulesProvider("http://example.com")
    content = "<h1>A</h1><h1>B</h1>"
    stack = RepoStackInfo(framework="static", package_manager="none", has_build_script=False, build_script=None)
    issues = [
        Issue(
            issue_id="1",
            rule_id="duplicate_h1",
            severity="medium",
            page_url="http://example.com",
            evidence="2 h1",
            suggested_fix="one h1",
        )
    ]
    r = p.fix_file(rel_path="page.html", content=content, issues=issues, repo_stack=stack, site_url="http://example.com")
    assert r.content is not None
    assert r.content.count("<h1") == 1
    assert "<h2" in r.content
