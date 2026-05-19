from __future__ import annotations

from app.orchestrator.context import Issue
from app.services.fix_provider.base import FixFileResult, FixProvider
from app.services.fix_provider.openai_compat import OpenAICompatProvider
from app.services.fix_provider.rules import RulesProvider
from app.services.repo_stack import RepoStackInfo


class ChainProvider(FixProvider):
    name = "chain"

    def __init__(self, site_url: str) -> None:
        self._rules = RulesProvider(site_url)
        self._openai = OpenAICompatProvider()

    def fix_file(
        self,
        *,
        rel_path: str,
        content: str,
        issues: list[Issue],
        repo_stack: RepoStackInfo,
        site_url: str,
    ) -> FixFileResult:
        r = self._rules.fix_file(
            rel_path=rel_path,
            content=content,
            issues=issues,
            repo_stack=repo_stack,
            site_url=site_url,
        )
        if r.content is not None:
            return r
        o = self._openai.fix_file(
            rel_path=rel_path,
            content=content,
            issues=issues,
            repo_stack=repo_stack,
            site_url=site_url,
        )
        if o.content is not None:
            o.provider = "chain:openai"
        return o
