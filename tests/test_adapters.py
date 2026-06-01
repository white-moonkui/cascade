"""Tests for Anthropic, CrewAI, and MCP adapters."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from typing import Any

import pytest

from cascade import DecisionPipeline
from cascade._store import Store
from cascade.adapters._base import GuardResult


# ═══════════════════════════════════════════════════════════════════
# Mock helpers — simulate SDK types without installing packages
# ═══════════════════════════════════════════════════════════════════


@dataclass
class MockToolUseBlock:
    """Simulates Anthropic's ToolUseBlock."""
    id: str
    name: str
    input: dict = field(default_factory=dict)
    type: str = "tool_use"


@dataclass
class MockTextBlock:
    """Simulates Anthropic's TextBlock."""
    text: str
    type: str = "text"


@dataclass
class MockAnthropicMessage:
    """Simulates Anthropic's Message."""
    content: list
    id: str = "msg_001"


class MockAnthropicClient:
    """Simulates Anthropic's client."""
    def __init__(self):
        class Messages:
            def create(self, **kwargs):
                return MockAnthropicMessage(content=[
                    MockTextBlock(text="Let me search."),
                    MockToolUseBlock(id="tu_1", name="web_search", input={"q": "hello"}),
                    MockToolUseBlock(id="tu_2", name="delete_file", input={"path": "/tmp/x"}),
                ])
        self.messages = Messages()


@dataclass
class MockCrewOutput:
    """Simulates a CrewAI task output with tool calls."""
    tool_calls: list[dict] = field(default_factory=list)


class MockCrew:
    """Simulates a CrewAI Crew."""
    def __init__(self, output=None):
        self._output = output or MockCrewOutput(tool_calls=[
            {"id": "ct_1", "name": "search", "args": {"q": "test"}},
            {"id": "ct_2", "name": "delete", "args": {"path": "/tmp/x"}},
        ])

    def kickoff(self):
        return self._output


class MockFastMCPServer:
    """Simulates a FastMCP server."""
    def __init__(self):
        self._tools = {}

    def tool(self, name=None):
        def decorator(func):
            tname = name or func.__name__
            self._tools[tname] = func
            return func
        return decorator


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def pipe():
    return DecisionPipeline(store=Store(store_dir=tempfile.mkdtemp()))


# ═══════════════════════════════════════════════════════════════════
# Anthropic adapter
# ═══════════════════════════════════════════════════════════════════


class TestAnthropicAdapter:
    def test_guard_response_filters_blocked(self, pipe):
        from cascade.adapters.anthropic import guard_anthropic_response
        msg = MockAnthropicMessage(content=[
            MockTextBlock(text="OK"),
            MockToolUseBlock(id="tu_1", name="web_search", input={"q": "hello"}),
            MockToolUseBlock(id="tu_2", name="danger", input={}),
        ])
        guarded = guard_anthropic_response(
            msg, pipeline=pipe,
            rules=[{"field": "name", "op": "nin", "value": ["danger"]}],
            strategy="threshold", min_score=0.0,
        )
        remaining = [b for b in guarded.content if b.type == "tool_use"]
        assert len(remaining) == 1
        assert remaining[0].name == "web_search"

    def test_guard_response_all_blocked_raises(self, pipe):
        from cascade.adapters.anthropic import guard_anthropic_response
        msg = MockAnthropicMessage(content=[
            MockToolUseBlock(id="tu_1", name="danger", input={}),
        ])
        with pytest.raises(RuntimeError, match="blocked by cascade"):
            guard_anthropic_response(
                msg, pipeline=pipe,
                rules=[{"field": "name", "op": "nin", "value": ["danger"]}],
            )

    def test_guard_response_skip_on_blocked(self, pipe):
        from cascade.adapters.anthropic import guard_anthropic_response
        msg = MockAnthropicMessage(content=[
            MockTextBlock(text="hi"),
            MockToolUseBlock(id="tu_1", name="danger", input={}),
        ])
        guarded = guard_anthropic_response(
            msg, pipeline=pipe,
            rules=[{"field": "name", "op": "nin", "value": ["danger"]}],
            on_blocked="skip",
        )
        assert all(b.type != "tool_use" for b in guarded.content)
        assert any(b.type == "text" for b in guarded.content)

    def test_guard_response_no_tool_blocks(self, pipe):
        from cascade.adapters.anthropic import guard_anthropic_response
        msg = MockAnthropicMessage(content=[MockTextBlock(text="hello")])
        result = guard_anthropic_response(msg, pipeline=pipe)
        assert result is msg

    def test_wrap_client_auto_governs(self, pipe):
        from cascade.adapters.anthropic import wrap_anthropic_client
        client = wrap_anthropic_client(
            MockAnthropicClient(), pipeline=pipe,
            rules=[{"field": "name", "op": "nin", "value": ["delete_file"]}],
            strategy="threshold", min_score=0.0,
        )
        resp = client.messages.create(model="test", max_tokens=100, messages=[])
        remaining = [b for b in resp.content if b.type == "tool_use"]
        assert len(remaining) == 1
        assert remaining[0].name == "web_search"


# ═══════════════════════════════════════════════════════════════════
# CrewAI adapter
# ═══════════════════════════════════════════════════════════════════


class TestCrewAIAdapter:
    def test_guard_output_filters_blocked(self, pipe):
        from cascade.adapters.crewai import guard_crew_output
        output = MockCrewOutput(tool_calls=[
            {"id": "ct_1", "name": "search", "args": {"q": "test"}},
            {"id": "ct_2", "name": "delete", "args": {"path": "/tmp/x"}},
        ])
        guarded = guard_crew_output(
            output, pipeline=pipe,
            rules=[{"field": "name", "op": "nin", "value": ["delete"]}],
            strategy="threshold", min_score=0.0,
        )
        assert len(guarded.tool_calls) == 1
        assert guarded.tool_calls[0]["name"] == "search"

    def test_guard_output_all_blocked(self, pipe):
        from cascade.adapters.crewai import guard_crew_output
        output = MockCrewOutput(tool_calls=[
            {"id": "ct_1", "name": "delete", "args": {}},
        ])
        guarded = guard_crew_output(
            output, pipeline=pipe,
            rules=[{"field": "name", "op": "nin", "value": ["delete"]}],
            strategy="threshold", min_score=0.0,
        )
        assert guarded.tool_calls == []

    def test_guard_output_no_tool_calls(self, pipe):
        from cascade.adapters.crewai import guard_crew_output
        output = MockCrewOutput(tool_calls=[])
        assert guard_crew_output(output, pipeline=pipe) is output

    def test_wrap_crew(self, pipe):
        from cascade.adapters.crewai import wrap_crew
        crew = MockCrew(output=MockCrewOutput(tool_calls=[
            {"id": "ct_1", "name": "search", "args": {}},
            {"id": "ct_2", "name": "delete", "args": {}},
        ]))
        guarded_crew = wrap_crew(
            crew, pipeline=pipe,
            rules=[{"field": "name", "op": "nin", "value": ["delete"]}],
            strategy="threshold", min_score=0.0,
        )
        result = guarded_crew.kickoff()
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search"


# ═══════════════════════════════════════════════════════════════════
# MCP adapter
# ═══════════════════════════════════════════════════════════════════


class TestMCPAdapter:
    def test_guarded_tool_sync_allowed(self, pipe):
        from cascade.adapters.mcp import guarded_tool

        @guarded_tool(name="search", pipeline=pipe, strategy="threshold", min_score=0.0)
        def search(query: str) -> str:
            return f"Results for {query}"

        assert search(query="hello") == "Results for hello"

    def test_guarded_tool_sync_blocked(self, pipe):
        from cascade.adapters.mcp import guarded_tool

        @guarded_tool(
            name="danger", pipeline=pipe,
            rules=[{"field": "name", "op": "nin", "value": ["danger"]}],
        )
        def danger() -> str:
            return "should not run"

        with pytest.raises(RuntimeError, match="blocked by cascade"):
            danger()

    def test_guarded_tool_async(self, pipe):
        import asyncio
        from cascade.adapters.mcp import guarded_tool

        @guarded_tool(name="async_search", pipeline=pipe, strategy="threshold", min_score=0.0)
        async def async_search(q: str) -> str:
            return f"Async: {q}"

        result = asyncio.run(async_search(q="test"))
        assert result == "Async: test"

    def test_guarded_tool_skip_on_blocked(self, pipe):
        from cascade.adapters.mcp import guarded_tool

        @guarded_tool(
            name="danger", pipeline=pipe,
            rules=[{"field": "name", "op": "nin", "value": ["danger"]}],
            skip_on_blocked=True,
        )
        def danger() -> str:
            return "should not run"

        result = danger()
        assert "Blocked" in result

    def test_server_guard_install(self, pipe):
        from cascade.adapters.mcp import MCPServerGuard

        server = MockFastMCPServer()
        guard = MCPServerGuard(server, pipeline=pipe, rules=[], strategy="threshold", min_score=0.0)
        guard.install()

        @server.tool(name="safe_tool")
        def safe_tool(x: int) -> int:
            return x * 2

        assert "safe_tool" in server._tools
        # The handler should be wrapped — calling it should still work
        from cascade.adapters.mcp import guarded_tool
        assert callable(server._tools["safe_tool"])

        guard.uninstall()
        assert server.tool is not guard.install  # original restored


# ═══════════════════════════════════════════════════════════════════
# GuardResult smoke tests (from _base)
# ═══════════════════════════════════════════════════════════════════


class TestGuardResult:
    def test_allowed(self):
        r = GuardResult({"selected": [{"id": "a"}], "rejected": []})
        assert r.allowed == [{"id": "a"}]
        assert r.allowed_ids == {"a"}
        assert r.all_blocked is False

    def test_all_blocked(self):
        r = GuardResult({"selected": [], "rejected": [{"id": "a", "reason": "nope"}]})
        assert r.all_blocked is True
        assert r.blocked == [{"id": "a", "reason": "nope"}]

    def test_audit_id(self):
        r = GuardResult({"audit_id": "abc123"})
        assert r.audit_id == "abc123"
