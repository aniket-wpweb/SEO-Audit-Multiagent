"""Progress sink events from run_pipeline."""

from __future__ import annotations

import pytest

from app.orchestrator.context import AnalyzeRequest, RunContext
from app.orchestrator.registry import ToolRegistry
from app.orchestrator.runner import run_pipeline


def test_progress_sink_pre_validation_and_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.orchestrator.runner.validate_pre_analyze", lambda ctx: None)
    monkeypatch.setattr("app.agents.planner.build_plan", lambda req: ["noop"])

    reg = ToolRegistry()
    reg.register("noop", lambda ctx: None)

    sink: list = []
    ctx = RunContext(request=AnalyzeRequest(url="http://example.com", depth=0, max_pages=1))
    run_pipeline(ctx, reg=reg, progress_sink=sink)

    steps_states = [(e["step"], e["state"]) for e in sink]
    assert ("pre_validation", "running") in steps_states
    assert ("pre_validation", "done") in steps_states
    assert ("noop", "running") in steps_states
    assert ("noop", "done") in steps_states
    assert ("post_build", "running") in steps_states
    assert ("post_build", "done") in steps_states


def test_progress_sink_pre_validation_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(ctx: RunContext) -> None:
        raise ValueError("bad url")

    monkeypatch.setattr("app.orchestrator.runner.validate_pre_analyze", boom)

    sink: list = []
    ctx = RunContext(request=AnalyzeRequest(url="http://example.com", depth=0, max_pages=1))
    run_pipeline(ctx, reg=ToolRegistry(), progress_sink=sink)

    assert sink[0]["step"] == "pre_validation" and sink[0]["state"] == "running"
    assert sink[1]["step"] == "pre_validation" and sink[1]["state"] == "failed"
    assert ctx.fatal_error is not None
