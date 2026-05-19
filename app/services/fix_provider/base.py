from __future__ import annotations

from dataclasses import dataclass

from app.orchestrator.context import Issue
from app.services.repo_stack import RepoStackInfo


@dataclass
class FixFileResult:
    content: str | None
    reason: str = ""
    provider: str = ""


class FixProvider:
    name: str = "base"

    def fix_file(
        self,
        *,
        rel_path: str,
        content: str,
        issues: list[Issue],
        repo_stack: RepoStackInfo,
        site_url: str,
    ) -> FixFileResult:
        raise NotImplementedError
