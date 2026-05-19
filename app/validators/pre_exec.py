from __future__ import annotations

import shutil
from urllib.parse import urljoin, urlparse

from app.orchestrator.context import AnalyzeRequest


def validate_pre_analyze(ctx) -> None:
    req: AnalyzeRequest = ctx.request
    u = urlparse(req.url)
    if u.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed")
    if req.apply_fixes and not req.dry_run:
        if not (req.repo_url or "").strip():
            raise ValueError("repo_url is required when apply_fixes is true and dry_run is false")
        from app.services.git_repo import (
            assert_clone_destination_allowed,
            clone_and_checkout_branch,
            clone_base_dir,
            default_git_branch,
            validate_repo_url,
        )

        url = validate_repo_url(req.repo_url or "")
        branch = default_git_branch(req.git_branch)
        dest = clone_base_dir() / ctx.run_id
        assert_clone_destination_allowed(dest, ctx.run_id)
        ctx.git_branch = branch
        try:
            clone_and_checkout_branch(url, dest, branch)
        except BaseException:
            shutil.rmtree(dest, ignore_errors=True)
            raise
        ctx.repo_path = dest


def same_origin(base: str, link: str) -> bool:
    a, b = urlparse(base), urlparse(urljoin(base, link))
    if not b.netloc:
        return True
    return a.netloc == b.netloc
