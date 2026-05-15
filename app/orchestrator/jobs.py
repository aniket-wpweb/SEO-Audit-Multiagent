"""In-memory async analyze jobs (workshop / local use only)."""

from __future__ import annotations

import threading
import time
from typing import Any
from uuid import uuid4

from app.orchestrator.context import AnalyzeRequest, RunContext
from app.orchestrator.runner import run_pipeline

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_JOB_TIMES: dict[str, float] = {}

TTL_SEC = 3600
_MAX_JOBS = 200


def _cleanup_old() -> None:
    now = time.time()
    with _LOCK:
        dead = [jid for jid, t in _JOB_TIMES.items() if now - t > TTL_SEC]
        for jid in dead:
            _JOBS.pop(jid, None)
            _JOB_TIMES.pop(jid, None)
        if len(_JOBS) > _MAX_JOBS:
            # drop oldest by timestamp
            sorted_ids = sorted(_JOB_TIMES.keys(), key=lambda k: _JOB_TIMES[k])[: len(_JOBS) - _MAX_JOBS + 50]
            for jid in sorted_ids:
                _JOBS.pop(jid, None)
                _JOB_TIMES.pop(jid, None)


def start_job(body: AnalyzeRequest) -> str:
    """Start run_pipeline in a daemon thread; returns job_id."""
    _cleanup_old()
    job_id = str(uuid4())
    events: list[dict[str, Any]] = []
    with _LOCK:
        _JOBS[job_id] = {
            "events": events,
            "done": False,
            "ctx": None,
            "worker_error": None,
        }
        _JOB_TIMES[job_id] = time.time()

    def work() -> None:
        try:
            ctx = RunContext(request=body)
            run_pipeline(ctx, progress_sink=events)
            with _LOCK:
                _JOBS[job_id]["ctx"] = ctx
        except Exception as e:  # pragma: no cover - defensive
            with _LOCK:
                _JOBS[job_id]["worker_error"] = str(e)
        finally:
            with _LOCK:
                _JOBS[job_id]["done"] = True
                _JOB_TIMES[job_id] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return job_id


def get_snapshot(job_id: str, since: int = 0) -> dict[str, Any] | None:
    """Return job state; events lists only entries with index >= since."""
    with _LOCK:
        j = _JOBS.get(job_id)
        if j is None:
            return None
        ev: list = j["events"]
        safe_since = max(0, since)
        new_events = list(ev[safe_since:]) if safe_since <= len(ev) else []
        out: dict[str, Any] = {
            "done": j["done"],
            "events": new_events,
            "total_events": len(ev),
        }
        if j["done"]:
            err = j.get("worker_error")
            if err:
                out["http_status"] = 500
                out["response"] = {
                    "status": "failed",
                    "error": {"error_code": "worker", "message": err},
                    "plan": [],
                    "results": {},
                }
            elif j.get("ctx") is not None:
                from app.orchestrator.response import analyze_result_dict

                ctx: RunContext = j["ctx"]
                code, payload = analyze_result_dict(ctx)
                out["http_status"] = code
                out["response"] = payload
            else:
                out["http_status"] = 500
                out["response"] = {
                    "status": "failed",
                    "error": {"error_code": "internal", "message": "missing result context"},
                    "plan": [],
                    "results": {},
                }
        else:
            out["http_status"] = None
            out["response"] = None
        return out
