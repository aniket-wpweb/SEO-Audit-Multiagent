"""Clone remote Git repositories and work on the ``test`` branch (workshop apply flow)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def _seo_agent_root() -> Path:
    """seo-agent/ directory (parent of app/)."""
    return Path(__file__).resolve().parent.parent.parent


def clone_base_dir() -> Path:
    """Directory under which per-run clone folders are created."""
    raw = os.environ.get("SEO_AGENT_CLONE_ROOT", ".clones").strip() or ".clones"
    p = Path(raw)
    base = p.resolve() if p.is_absolute() else (_seo_agent_root() / p).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def assert_clone_destination_allowed(dest: Path, run_id: str) -> Path:
    """Ensure dest is exactly ``clone_base_dir() / run_id`` (prevents path escape)."""
    expected = (clone_base_dir() / run_id).resolve()
    resolved = dest.resolve()
    if resolved != expected:
        raise PermissionError(f"clone destination must be {expected}, got {resolved}")
    return resolved


def validate_repo_url(raw: str) -> str:
    """Return stripped URL; raise ValueError if not an allowed Git remote form."""
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
    r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError("git is not available on PATH")


def clone_and_checkout_test(repo_url: str, dest: Path) -> None:
    """
    Fresh clone into ``dest`` (must not exist as a repo target), then checkout ``test``:
    use ``origin/test`` if present after fetch, else existing ``test``, else create ``test``.
    """
    ensure_git_on_path()
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cp = subprocess.run(
        ["git", "clone", repo_url, str(dest)],
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("SEO_AGENT_GIT_CLONE_TIMEOUT_SEC", "600")),
    )
    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout or "unknown error")[:1200]
        raise RuntimeError(f"git clone failed: {msg}")

    subprocess.run(
        ["git", "fetch", "origin"],
        cwd=str(dest),
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("SEO_AGENT_GIT_FETCH_TIMEOUT_SEC", "300")),
    )

    remote_test = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/test"],
        cwd=str(dest),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if remote_test.returncode == 0:
        checkout = subprocess.run(
            ["git", "checkout", "-B", "test", "origin/test"],
            cwd=str(dest),
            capture_output=True,
            text=True,
            timeout=120,
        )
    else:
        local_test = subprocess.run(
            ["git", "rev-parse", "--verify", "test"],
            cwd=str(dest),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if local_test.returncode == 0:
            checkout = subprocess.run(
                ["git", "checkout", "test"],
                cwd=str(dest),
                capture_output=True,
                text=True,
                timeout=120,
            )
        else:
            checkout = subprocess.run(
                ["git", "checkout", "-b", "test"],
                cwd=str(dest),
                capture_output=True,
                text=True,
                timeout=120,
            )
    if checkout.returncode != 0:
        msg = (checkout.stderr or checkout.stdout or "unknown error")[:1200]
        raise RuntimeError(f"git checkout test failed: {msg}")


def try_commit_automated_fixes(repo: Path) -> tuple[str | None, str | None]:
    """
    If there are unstaged/staged changes, ``git add -A`` and commit.
    Returns (rev_parse_short_sha_or_None, error_message_or_None).
    """
    ensure_git_on_path()
    st = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if st.returncode != 0:
        return None, (st.stderr or st.stdout or "git status failed")[:500]
    if not st.stdout.strip():
        return None, None
    add = subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, text=True, timeout=120)
    if add.returncode != 0:
        return None, (add.stderr or add.stdout or "git add failed")[:500]
    msg = "seo-agent: automated fixes on test branch"
    cm = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (cm.stdout or "") + (cm.stderr or "")
    if cm.returncode != 0 and "nothing to commit" in out.lower():
        return None, None
    if cm.returncode != 0:
        return None, out[:800]
    rev = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=30,
    )
    sha = rev.stdout.strip() if rev.returncode == 0 else None
    return sha, None


def try_push_origin_test(repo: Path) -> tuple[bool, str | None]:
    """
    Run ``git push -u origin test`` from ``repo``.
    Returns (success, error_message_or_None). Requires credentials (SSH, credential helper, or token URL).
    """
    ensure_git_on_path()
    p = subprocess.run(
        ["git", "push", "-u", "origin", "test"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("SEO_AGENT_GIT_PUSH_TIMEOUT_SEC", "300")),
    )
    if p.returncode != 0:
        msg = (p.stderr or p.stdout or "git push failed")[:2000]
        return False, msg
    return True, None
