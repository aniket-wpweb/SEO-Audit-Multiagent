from app.orchestrator.context import AnalyzeRequest


def build_plan(req: AnalyzeRequest) -> list[str]:
    steps = ["crawl", "detect_stack", "seo_audit", "sop_validate"]
    if req.apply_fixes and not req.dry_run and ((req.repo_root or "").strip() or (req.repo_url or "").strip()):
        steps.append("code_modify")
    steps.append("format_results")
    return steps
