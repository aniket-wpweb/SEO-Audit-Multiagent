from __future__ import annotations

from app.orchestrator.context import RunContext, StackInfo


def run(ctx: RunContext) -> None:
    html = ctx.pages[0].html if ctx.pages else ""
    label = "unknown"
    confidence = "low"
    if "__NEXT_DATA__" in html or "/_next/" in html or "next/font" in html:
        label = "nextjs"
        confidence = "high"
    elif "react" in html.lower() and "reactroot" in html.lower():
        label = "react"
        confidence = "medium"
    elif ".php" in html.lower():
        label = "php"
        confidence = "medium"
    ctx.stack = StackInfo(label=label, confidence=confidence)
