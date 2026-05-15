import os

import pytest

from app.services.allowlist import assert_repo_allowed, load_allowlist_roots


def test_load_allowlist_defaults(monkeypatch):
    monkeypatch.delenv("SEO_AGENT_REPO_ALLOWLIST", raising=False)
    roots = load_allowlist_roots()
    assert any(r.name == "sample-site" for r in roots)


def test_assert_repo_allowed_relative(monkeypatch):
    monkeypatch.setenv("SEO_AGENT_REPO_ALLOWLIST", "sample-site")
    p = assert_repo_allowed("sample-site")
    assert p.name == "sample-site"


def test_assert_repo_allowed_rejects_outside(monkeypatch, tmp_path):
    monkeypatch.setenv("SEO_AGENT_REPO_ALLOWLIST", "sample-site")
    bad = tmp_path / "not-allowed-repo"
    bad.mkdir()
    with pytest.raises(PermissionError):
        assert_repo_allowed(str(bad))
