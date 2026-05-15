from __future__ import annotations

import json

from app.orchestrator.context import RunContext, SopRow
from app.rag.chroma_store import ChromaSopStore
from app.services.llm_provider import LLMProvider


def _rules_fallback(issue_rule: str, snippets: list[str]) -> SopRow:
    ref = snippets[0][:200] if snippets else "SOP"
    if issue_rule in ("missing_meta", "duplicate_h1", "missing_alt", "broken_link"):
        return SopRow(
            issue_id="",
            sop_status="violation",
            sop_reference=ref,
            sop_snippet=ref,
        )
    return SopRow(issue_id="", sop_status="needs_review", sop_reference=ref, sop_snippet=ref)


def run(ctx: RunContext) -> None:
    store = ChromaSopStore(llm=LLMProvider())
    llm = LLMProvider()
    rows: list[SopRow] = []
    for issue in ctx.issues:
        hits = store.similarity_search(f"{issue.rule_id} {issue.evidence}", k=2)
        snippets = [h["text"][:400] for h in hits]
        meta = json.dumps({"rule_id": issue.rule_id, "evidence": issue.evidence[:500]})
        parsed = llm.ollama_json_chat(
            system="You label SEO audit rows vs SOP. Reply JSON only: {sop_status: violation|compliant|needs_review, sop_reference: string}",
            user=f"Issue:\n{meta}\n\nSOP excerpts:\n" + "\n---\n".join(snippets),
        )
        if parsed and "sop_status" in parsed:
            rows.append(
                SopRow(
                    issue_id=issue.issue_id,
                    sop_status=str(parsed.get("sop_status", "needs_review")),
                    sop_reference=str(parsed.get("sop_reference", snippets[0][:120] if snippets else "")),
                    sop_snippet=snippets[0][:300] if snippets else "",
                )
            )
        else:
            fb = _rules_fallback(issue.rule_id, snippets)
            rows.append(
                SopRow(
                    issue_id=issue.issue_id,
                    sop_status=fb.sop_status,
                    sop_reference=fb.sop_reference,
                    sop_snippet=fb.sop_snippet,
                )
            )
    ctx.sop_rows = rows
