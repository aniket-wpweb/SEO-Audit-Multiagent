from app.orchestrator.context import AnalyzeRequest, PageRecord, RunContext
from app.tools import seo_audit
from app.tools.seo_audit import _app_page_tsx_hint


def test_app_page_tsx_hint() -> None:
    assert _app_page_tsx_hint("http://x") == "app/page.tsx"
    assert _app_page_tsx_hint("http://x/") == "app/page.tsx"
    assert _app_page_tsx_hint("http://x/blog") == "app/blog/page.tsx"
    assert _app_page_tsx_hint("http://x/blog/") == "app/blog/page.tsx"
    assert _app_page_tsx_hint("http://x/blog/post-1") == "app/blog/post-1/page.tsx"


def test_seo_audit_missing_alt_file_hint_for_nested_path() -> None:
    html = (
        "<html><head><title>t</title><meta name=\"description\" content=\"d\"></head>"
        '<body><img src="a.jpg" alt="" /></body></html>'
    )
    ctx = RunContext(request=AnalyzeRequest(url="http://example.com"))
    ctx.pages = [PageRecord(url="http://example.com/blog", status_code=200, html=html)]
    seo_audit.run(ctx)
    alts = [i for i in ctx.issues if i.rule_id == "missing_alt"]
    assert len(alts) == 1
    assert alts[0].file_hint == "app/blog/page.tsx"


def test_seo_audit_duplicate_h1_and_missing_description():
    html = "<html><head><title>t</title></head><body><h1>a</h1><h1>b</h1></body></html>"
    ctx = RunContext(request=AnalyzeRequest(url="http://example.com"))
    ctx.pages = [PageRecord(url="http://example.com", status_code=200, html=html)]
    seo_audit.run(ctx)
    rules = {i.rule_id for i in ctx.issues}
    assert "duplicate_h1" in rules
    assert "missing_meta" in rules
