"""Async analyze job API."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_analyze_async_pre_validation_fails_fast(client: TestClient) -> None:
    r = client.post(
        "/analyze/async",
        json={
            "url": "ftp://invalid-scheme",
            "depth": 0,
            "max_pages": 1,
            "dry_run": False,
            "apply_fixes": False,
            "repo_root": None,
            "repo_url": None,
        },
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    assert job_id
    data = None
    for _ in range(200):
        p = client.get(f"/analyze/jobs/{job_id}", params={"since": 0})
        assert p.status_code == 200
        data = p.json()
        if data["done"]:
            break
        time.sleep(0.02)
    assert data is not None and data["done"]
    assert data["response"]["status"] == "failed"
    assert data["http_status"] == 400
    events = data["events"]
    assert any(e.get("step") == "pre_validation" and e.get("state") == "failed" for e in events)


def test_analyze_job_unknown(client: TestClient) -> None:
    assert client.get("/analyze/jobs/not-a-real-uuid").status_code == 404
