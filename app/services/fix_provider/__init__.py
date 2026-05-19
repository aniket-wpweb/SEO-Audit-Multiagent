from __future__ import annotations

import os

from app.services.fix_provider.base import FixFileResult, FixProvider
from app.services.fix_provider.chain import ChainProvider
from app.services.fix_provider.openai_compat import OpenAICompatProvider
from app.services.fix_provider.rules import RulesProvider


def get_fix_provider(site_url: str) -> FixProvider:
    mode = os.environ.get("SEO_FIX_PROVIDER", "chain").strip().lower()
    if mode == "openai":
        return OpenAICompatProvider()
    if mode == "rules":
        return RulesProvider(site_url)
    return ChainProvider(site_url)


__all__ = ["FixFileResult", "FixProvider", "get_fix_provider"]
