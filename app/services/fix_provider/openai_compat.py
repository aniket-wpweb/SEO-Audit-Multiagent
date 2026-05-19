from __future__ import annotations

import json
import os
import httpx

from app.orchestrator.context import Issue
from app.services.fix_provider.base import FixFileResult, FixProvider
from app.services.repo_stack import RepoStackInfo

MAX_FILE_CHARS = 80_000


class OpenAICompatProvider(FixProvider):
    name = "openai"

    def __init__(self) -> None:
        self._api_key = os.environ.get("SEO_FIX_API_KEY", "").strip()
        self._base = os.environ.get("SEO_FIX_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self._model = os.environ.get("SEO_FIX_MODEL", "gpt-4o-mini")

    def fix_file(
        self,
        *,
        rel_path: str,
        content: str,
        issues: list[Issue],
        repo_stack: RepoStackInfo,
        site_url: str,
    ) -> FixFileResult:
        if not self._api_key:
            return FixFileResult(content=None, reason="SEO_FIX_API_KEY not set", provider=self.name)
        if len(content) > MAX_FILE_CHARS:
            return FixFileResult(content=None, reason="file_too_large", provider=self.name)

        issue_lines = "\n".join(
            f"- rule_id={i.rule_id} page={i.page_url} evidence={i.evidence[:200]} fix={i.suggested_fix[:200]}"
            for i in issues
        )
        system = (
            "You fix SEO issues in source files. Reply with JSON only: "
            '{"content": "<full updated file content>"}. '
            "Preserve valid syntax. Make minimal changes. Do not add markdown fences."
        )
        user = (
            f"Site URL: {site_url}\n"
            f"Framework: {repo_stack.framework}\n"
            f"File: {rel_path}\n\n"
            f"Issues:\n{issue_lines}\n\n"
            f"Current file:\n```\n{content}\n```"
        )
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(
                    f"{self._base}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                r.raise_for_status()
                data = r.json()
                raw = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw)
                new_content = parsed.get("content")
                if not isinstance(new_content, str) or not new_content.strip():
                    return FixFileResult(content=None, reason="empty_llm_content", provider=self.name)
                if new_content == content:
                    return FixFileResult(content=None, reason="unchanged", provider=self.name)
                if len(new_content) > len(content) * 3 + 1000:
                    return FixFileResult(content=None, reason="suspicious_size", provider=self.name)
                return FixFileResult(content=new_content, reason="ok", provider=self.name)
        except Exception as e:
            return FixFileResult(content=None, reason=str(e)[:300], provider=self.name)
