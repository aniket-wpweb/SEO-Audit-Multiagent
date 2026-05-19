"""Run apply pipeline against repo_url (local smoke test)."""
from __future__ import annotations

import json
import sys
import time
import urllib.request

from app.orchestrator.context import AnalyzeRequest, RunContext
from app.orchestrator.response import analyze_result_dict
from app.orchestrator.runner import run_pipeline


def run_local(url: str, repo_url: str) -> int:
    ctx = RunContext(
        request=AnalyzeRequest(
            url=url,
            depth=2,
            max_pages=10,
            apply_fixes=True,
            dry_run=False,
            repo_url=repo_url,
        )
    )
    events: list[dict] = []
    run_pipeline(ctx, progress_sink=events)
    code, payload = analyze_result_dict(ctx)
    print(json.dumps({"http_status": code, "events": events[-15:], "response": payload}, indent=2)[:12000])
    return 0 if code == 200 else 1


def run_api(base: str, url: str, repo_url: str) -> int:
    body = json.dumps(
        {
            "url": url,
            "depth": 2,
            "max_pages": 10,
            "apply_fixes": True,
            "dry_run": False,
            "repo_url": repo_url,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/analyze/async",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        start = json.loads(resp.read())
    job_id = start["job_id"]
    since = 0
    for _ in range(300):
        with urllib.request.urlopen(f"{base}/analyze/jobs/{job_id}?since={since}", timeout=30) as resp:
            snap = json.loads(resp.read())
        since = snap["total_events"]
        if snap.get("done"):
            payload = snap.get("response") or {}
            print(json.dumps(payload, indent=2)[:12000])
            return 0 if payload.get("status") == "completed" else 1
        time.sleep(0.7)
    print("timeout waiting for job")
    return 1


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    repo = sys.argv[2] if len(sys.argv) > 2 else "https://github.com/aniket-wpweb/test-website.git"
    mode = sys.argv[3] if len(sys.argv) > 3 else "local"
    if mode == "api":
        raise SystemExit(run_api("http://127.0.0.1:8030", target_url, repo))
    raise SystemExit(run_local(target_url, repo))
