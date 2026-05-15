"""Map tool id -> callable(ctx: RunContext) -> None; mutates ctx."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.orchestrator.context import RunContext


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[["RunContext"], None]] = {}

    def register(self, tool_id: str, fn: Callable[["RunContext"], None]) -> None:
        self._handlers[tool_id] = fn

    def get(self, tool_id: str) -> Callable[["RunContext"], None]:
        if tool_id not in self._handlers:
            raise KeyError(f"Unknown tool: {tool_id}")
        return self._handlers[tool_id]
