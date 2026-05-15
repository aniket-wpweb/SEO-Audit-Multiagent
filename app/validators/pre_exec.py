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
        has_root = bool((req.repo_root or "").strip())
        has_url = bool((req.repo_url or "").strip())
        if has_root and has_url:
            raise ValueError("Provide only one of repo_root or repo_url, not both")
        if not has_root and not has_url:
            raise ValueError(
                "repo_root or repo_url is required when apply_fixes is true and dry_run is false",
            )
        if has_url:
            from app.services.git_repo import (
                assert_clone_destination_allowed,
                clone_and_checkout_test,
                clone_base_dir,
                validate_repo_url,
            )

            url = validate_repo_url(req.repo_url or "")
            dest = clone_base_dir() / ctx.run_id
            assert_clone_destination_allowed(dest, ctx.run_id)
            try:
                clone_and_checkout_test(url, dest)
            except BaseException:
                shutil.rmtree(dest, ignore_errors=True)
                raise
            ctx.repo_path = dest
        else:
            from app.services.allowlist import assert_repo_allowed

            ctx.repo_path = assert_repo_allowed(req.repo_root)


def same_origin(base: str, link: str) -> bool:
    a, b = urlparse(base), urlparse(urljoin(base, link))
    if not b.netloc:
        return True
    return a.netloc == b.netloc
