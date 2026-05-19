"""Map SEO audit issues to repository source files for fixing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.orchestrator.context import Issue, RunContext
from app.services.repo_hints import expand_patch_targets, resolve_issue_file_hints
from app.services.repo_layout import analyze_repo_layout, join_posix_rel
from app.services.repo_stack import RepoStackInfo


@dataclass
class FixTarget:
    rel_path: str
    issues: list[Issue] = field(default_factory=list)


def _grep_issue_without_hint(repo: Path, layout, issue: Issue, max_hits: int = 5) -> list[str]:
    from app.services.repo_hints import grep_repo_for_substring

    needles: list[str] = []
    if issue.evidence:
        if len(issue.evidence) >= 8 and "<" in issue.evidence:
            needles.append(issue.evidence[:120])
        if issue.rule_id == "broken_link" and issue.evidence.startswith("href="):
            rest = issue.evidence[5:].split(" (")[0].strip()
            if rest:
                needles.append(rest)
    hits: list[str] = []
    for n in needles:
        hits.extend(grep_repo_for_substring(repo, layout, n, max_hits=max_hits))
    return list(dict.fromkeys(hits))[:max_hits]


def build_fix_targets(ctx: RunContext, repo_stack: RepoStackInfo) -> list[FixTarget]:
    repo = ctx.repo_path
    if repo is None:
        return []

    resolve_issue_file_hints(ctx)
    layout = analyze_repo_layout(repo)
    by_path: dict[str, list[Issue]] = {}

    for iss in ctx.issues:
        if iss.file_hint:
            rel = iss.file_hint.replace("\\", "/")
            by_path.setdefault(rel, []).append(iss)

    hinted_without_file: list[Issue] = []
    for iss in ctx.issues:
        if iss.file_hint:
            if not join_posix_rel(repo, iss.file_hint).is_file():
                hinted_without_file.append(iss)
        else:
            hinted_without_file.append(iss)

    expanded: dict[str, list[Issue]] = {}
    for rel, file_issues in by_path.items():
        for t in expand_patch_targets(repo, layout, rel, file_issues):
            expanded.setdefault(t, []).extend(file_issues)

    for iss in hinted_without_file:
        if iss.file_hint and join_posix_rel(repo, iss.file_hint).is_file():
            continue
        for hit in _grep_issue_without_hint(repo, layout, iss):
            expanded.setdefault(hit, []).append(iss)

    out: list[FixTarget] = []
    seen: set[str] = set()
    for rel, issues in expanded.items():
        rel = rel.replace("\\", "/")
        if rel in seen or not join_posix_rel(repo, rel).is_file():
            continue
        seen.add(rel)
        dedup_issues: list[Issue] = []
        seen_ids: set[str] = set()
        for i in issues:
            if i.issue_id not in seen_ids:
                seen_ids.add(i.issue_id)
                dedup_issues.append(i)
        out.append(FixTarget(rel_path=rel, issues=dedup_issues))

    ctx.fix_plan = [{"file_path": t.rel_path, "issue_ids": [i.issue_id for i in t.issues]} for t in out]
    return out
