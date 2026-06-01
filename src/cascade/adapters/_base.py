"""Shared utilities for framework adapters.

Keeps individual adapters focused on their SDK's quirks while
reusing the tool-call conversion and guard-result shaping logic.
"""

from __future__ import annotations

import json
from typing import Any


class ToolCallConverter:
    """Bi-directional conversion between cascade dicts and SDK-native formats.

    Subclass or instantiate with *to_cascade* and *from_cascade* callables.
    """

    def __init__(
        self,
        to_cascade: list[dict] | None = None,
        from_cascade: list[dict] | None = None,
    ):
        self._to = to_cascade
        self._from = from_cascade

    @staticmethod
    def from_openai(tool_calls: list[Any]) -> list[dict]:
        """OpenAI SDK ``ChatCompletionMessageToolCall`` → cascade dicts."""
        return [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            }
            for tc in (tool_calls or [])
        ]

    @staticmethod
    def from_langchain(tool_calls: list[dict]) -> list[dict]:
        """LangChain ``AIMessage.tool_calls`` → cascade dicts."""
        return [
            {
                "id": tc.get("id", f"lc_{i}"),
                "name": tc["name"],
                "arguments": tc.get("args", {}),
                "confidence": tc.get("confidence", 0.0),
            }
            for i, tc in enumerate(tool_calls or [])
        ]


class GuardResult:
    """Wraps a ``guard()`` return dict so adapters can query it concisely."""

    def __init__(self, raw: dict):
        self._raw = raw

    @property
    def allowed(self) -> list[dict]:
        """Tool calls that passed governance (selected list)."""
        return self._raw.get("selected", [])

    @property
    def blocked(self) -> list[dict]:
        """Tool calls that were rejected."""
        return self._raw.get("rejected", [])

    @property
    def allowed_ids(self) -> set[str]:
        return {tc["id"] for tc in self.allowed}

    @property
    def all_blocked(self) -> bool:
        return len(self.allowed) == 0

    @property
    def audit_id(self) -> str | None:
        return self._raw.get("audit_id")
