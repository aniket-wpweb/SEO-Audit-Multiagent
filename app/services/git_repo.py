"""Clone remote Git repositories, apply fixes on a working branch, commit and push."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from app.services.subprocess_cmd import run_cmd


def _seo_agent_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def default_git_branch(request_branch: str | None = None) -> str:
    if request_branch and request_branch.strip():
        return request_branch.strip()
    return os.environ.get("SEO_AGENT_GIT_BRANCH", "seo-fixes").strip() or "seo-fixes"


def clone_base_dir() -> Path:
    raw = os.environ.get("SEO_AGENT_CLONE_ROOT", ".clones").strip() or ".clones"
    p = Path(raw)
    base = p.resolve() if p.is_absolute() else (_seo_agent_root() / p).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def assert_clone_destination_allowed(dest: Path, run_id: str) -> Path:
    expected = (clone_base_dir() / run_id).resolve()
    resolved = dest.resolve()
    if resolved != expected:
        raise PermissionError(f"clone destination must be {expected}, got {resolved}")
    return resolved


def validate_repo_url(raw: str) -> str:
    s = raw.strip()
    if not s:
        raise ValueError("repo_url is empty")
    low = s.lower()
    if low.startswith("file:"):
        raise ValueError("file:// URLs are not allowed")
    if s.startswith("git@"):
        at = s.find("@")
        colon = s.find(":", at + 1)
        if at < 0 or colon < 0 or colon == len(s) - 1:
            raise ValueError("Invalid git@ host:path URL")
        return s
    u = urlparse(s)
    if u.scheme in ("https", "http", "ssh") and u.netloc:
        return s
    raise ValueError("repo_url must be https://, http://, ssh://, or git@host:path")


def ensure_git_on_path() -> None:
    try:
        r = run_cmd(["git", "--version"], timeout=10)
    except FileNotFoundError as exc:
        raise RuntimeError("git is not available on PATH") from exc
    if r.returncode != 0:
        raise RuntimeError("git is not available on PATH")


def clone_and_checkout_branch(repo_url: str, dest: Path, branch: str) -> None:
    """Fresh clone, then checkout ``branch`` from origin or create it."""
    ensure_git_on_path()
    branch = branch.strip()
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cp = run_cmd(
        ["git", "clone", repo_url, str(dest)],
        timeout=int(os.environ.get("SEO_AGENT_GIT_CLONE_TIMEOUT_SEC", "600")),
    )
    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout or "unknown error")[:1200]
        raise RuntimeError(f"git clone failed: {msg}")

    run_cmd(
        ["git", "fetch", "origin"],
        cwd=str(dest),
        timeout=int(os.environ.get("SEO_AGENT_GIT_FETCH_TIMEOUT_SEC", "300")),
    )

    remote_ref = run_cmd(
        ["git", "rev-parse", "--verify", f"origin/{branch}"],
        cwd=str(dest),
        timeout=60,
    )
    if remote_ref.returncode == 0:
        checkout = run_cmd(
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            cwd=str(dest),
            timeout=120,
        )
    else:
        local_ref = run_cmd(
            ["git", "rev-parse", "--verify", branch],
            cwd=str(dest),
            timeout=60,
        )
        if local_ref.returncode == 0:
            checkout = run_cmd(
                ["git", "checkout", branch],
                cwd=str(dest),
                timeout=120,
            )
        else:
            checkout = run_cmd(
                ["git", "checkout", "-b", branch],
                cwd=str(dest),
                timeout=120,
            )
    if checkout.returncode != 0:
        msg = (checkout.stderr or checkout.stdout or "unknown error")[:1200]
        raise RuntimeError(f"git checkout {branch} failed: {msg}")


def clone_and_checkout_test(repo_url: str, dest: Path) -> None:
    """Backward-compatible alias."""
    clone_and_checkout_branch(repo_url, dest, "test")


def try_commit_automated_fixes(repo: Path, branch: str | None = None) -> tuple[str | None, str | None]:
    ensure_git_on_path()
    br = branch or default_git_branch()
    st = run_cmd(
        ["git", "status", "--porcelain"],
        cwd=str(repo),
        timeout=60,
    )
    if st.returncode != 0:
        return None, (st.stderr or st.stdout or "git status failed")[:500]
    if not st.stdout.strip():
        return None, None
    add = run_cmd(["git", "add", "-A"], cwd=str(repo), timeout=120)
    if add.returncode != 0:
        return None, (add.stderr or add.stdout or "git add failed")[:500]
    msg = f"seo-agent: automated SEO fixes on {br}"
    cm = run_cmd(
        ["git", "commit", "-m", msg],
        cwd=str(repo),
        timeout=120,
    )
    out = (cm.stdout or "") + (cm.stderr or "")
    if cm.returncode != 0 and "nothing to commit" in out.lower():
        return None, None
    if cm.returncode != 0:
        return None, out[:800]
    rev = run_cmd(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(repo),
        timeout=30,
    )
    sha = rev.stdout.strip() if rev.returncode == 0 else None
    return sha, None


def try_push_origin_branch(repo: Path, branch: str | None = None) -> tuple[bool, str | None]:
    br = branch or default_git_branch()
    ensure_git_on_path()
    p = run_cmd(
        ["git", "push", "-u", "origin", br],
        cwd=str(repo),
        timeout=int(os.environ.get("SEO_AGENT_GIT_PUSH_TIMEOUT_SEC", "300")),
    )
    if p.returncode != 0:
        return False, (p.stderr or p.stdout or "git push failed")[:2000]
    return True, None


def try_push_origin_test(repo: Path) -> tuple[bool, str | None]:
    return try_push_origin_branch(repo, "test")
