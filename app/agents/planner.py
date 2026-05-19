from app.orchestrator.context import AnalyzeRequest


def build_plan(req: AnalyzeRequest) -> list[str]:
    steps = ["crawl", "detect_stack", "seo_audit", "sop_validate"]
    if req.apply_fixes and not req.dry_run and (req.repo_url or "").strip():
        steps.append("seo_fix")
    return steps
