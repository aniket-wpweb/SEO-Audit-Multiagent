"""Git URL validation and clone-path helpers."""

from __future__ import annotations

import subprocess

import pytest

from app.services.git_repo import (
    assert_clone_destination_allowed,
    clone_base_dir,
    try_commit_automated_fixes,
    try_push_origin_test,
    validate_repo_url,
)


def test_validate_repo_url_https() -> None:
    assert validate_repo_url("  https://github.com/foo/bar.git  ") == "https://github.com/foo/bar.git"


def test_validate_repo_url_git_at() -> None:
    assert validate_repo_url("git@github.com:foo/bar.git") == "git@github.com:foo/bar.git"


def test_validate_repo_url_rejects_file() -> None:
    with pytest.raises(ValueError, match="file"):
        validate_repo_url("file:///etc/passwd")


def test_validate_repo_url_rejects_empty() -> None:
    with pytest.raises(ValueError):
        validate_repo_url("   ")


def test_assert_clone_destination_allowed_ok(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEO_AGENT_CLONE_ROOT", str(tmp_path))
    run_id = "run-test-123"
    dest = clone_base_dir() / run_id
    assert_clone_destination_allowed(dest, run_id)


def test_assert_clone_destination_allowed_rejects_escape(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEO_AGENT_CLONE_ROOT", str(tmp_path))
    run_id = "run-test-123"
    bad = tmp_path / "other"
    with pytest.raises(PermissionError):
        assert_clone_destination_allowed(bad, run_id)


def test_try_commit_automated_fixes_no_changes(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(repo), check=True)
    (repo / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True, capture_output=True)
    sha, err = try_commit_automated_fixes(repo)
    assert err is None
    assert sha is None


def test_try_commit_automated_fixes_with_change(tmp_path) -> None:
    repo = tmp_path / "r2"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(repo), check=True)
    (repo / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True, capture_output=True)
    (repo / "a.txt").write_text("y", encoding="utf-8")
    sha, err = try_commit_automated_fixes(repo)
    assert err is None
    assert sha is not None and len(sha) >= 4


def test_try_push_origin_test_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr("app.services.git_repo.ensure_git_on_path", lambda: None)
    recorded: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stderr = ""
            stdout = ""

        recorded.append(list(cmd))
        return R()

    monkeypatch.setattr("app.services.git_repo.run_cmd", fake_run)
    ok, err = try_push_origin_test(tmp_path)
    assert ok is True
    assert err is None
    assert recorded and recorded[0][1:] == ["push", "-u", "origin", "test"]


def test_try_push_origin_test_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr("app.services.git_repo.ensure_git_on_path", lambda: None)

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 1
            stderr = "auth failed"
            stdout = ""

        return R()

    monkeypatch.setattr("app.services.git_repo.run_cmd", fake_run)
    ok, err = try_push_origin_test(tmp_path)
    assert ok is False
    assert err and "auth" in err
