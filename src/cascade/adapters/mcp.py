"""MCP (Model Context Protocol) gateway — govern tool calls in MCP servers.

Entry-points
------------
``guarded_tool`` — decorator that wraps an MCP tool handler with cascade.
``MCPServerGuard`` — wraps a ``FastMCP`` server to guard all tools.

Usage
-----
.. code-block:: python

   from mcp.server.fastmcp import FastMCP
   from cascade import DecisionPipeline
   from cascade.adapters.mcp import guarded_tool

   pipe = DecisionPipeline(rules=[{"field": "name", "op": "nin", "value": ["danger"]}])

   @mcp.tool()
   @guarded_tool(name="search", pipeline=pipe)
   async def search(query: str) -> str:
       return f"Results for {query}"

Or guard all tools at once::

   from cascade.adapters.mcp import MCPServerGuard

   mcp = FastMCP("my-server")
   guard = MCPServerGuard(mcp, pipeline=pipe)
   guard.install()  # wraps every registered tool with governance
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Optional

from cascade import DecisionPipeline


def guarded_tool(
    name: Optional[str] = None,
    pipeline: Optional[DecisionPipeline] = None,
    rules: Optional[list[dict]] = None,
    skip_on_blocked: bool = False,
    **guard_kwargs: Any,
) -> Callable:
    """Decorator that wraps an MCP tool handler with cascade governance.

    Parameters
    ----------
    name:
        Tool name (used in cascade tool-call dicts).  Defaults to the
        decorated function's name.
    pipeline:
        A ``DecisionPipeline`` instance.  If omitted, a new one is
        created (no rules applied).
    rules:
        Rule list forwarded to ``pipeline.guard()``.
    skip_on_blocked:
        If ``True``, blocked calls return a safe fallback message
        instead of raising an error.
    **guard_kwargs:
        Extra keyword args passed to ``pipeline.guard()``.

    Usage
    -----
    .. code-block:: python

       @mcp.tool()
       @guarded_tool(pipeline=pipe, rules=BLOCKED_TOOLS)
       async def my_tool(param: str) -> str:
           ...
    """

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        _pipeline = pipeline or DecisionPipeline()

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                args_repr = _build_tool_call(tool_name, args, kwargs)
                result = _pipeline.guard(tool_calls=[args_repr], rules=rules or [], **guard_kwargs)
                if not result["selected"]:
                    if skip_on_blocked:
                        return f"[Blocked by cascade policy — {tool_name}]"
                    raise RuntimeError(
                        f"Tool `{tool_name}` blocked by cascade policy. "
                        f"Audit ID: {result.get('audit_id', 'N/A')}"
                    )
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                args_repr = _build_tool_call(tool_name, args, kwargs)
                result = _pipeline.guard(tool_calls=[args_repr], rules=rules or [], **guard_kwargs)
                if not result["selected"]:
                    if skip_on_blocked:
                        return f"[Blocked by cascade policy — {tool_name}]"
                    raise RuntimeError(
                        f"Tool `{tool_name}` blocked by cascade policy. "
                        f"Audit ID: {result.get('audit_id', 'N/A')}"
                    )
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


class MCPServerGuard:
    """Install cascade governance on all tools registered with a ``FastMCP`` server.

    Usage
    -----
    .. code-block:: python

       mcp = FastMCP("my-server")
       guard = MCPServerGuard(mcp, pipeline=pipe)
       guard.install()  # wraps every tool — just add @mcp.tool() as normal
    """

    def __init__(
        self,
        server: Any,
        pipeline: Optional[DecisionPipeline] = None,
        rules: Optional[list[dict]] = None,
        **guard_kwargs: Any,
    ):
        self._server = server
        self._pipeline = pipeline or DecisionPipeline()
        self._rules = rules
        self._guard_kwargs = guard_kwargs
        self._original_tool = None

    def install(self) -> None:
        """Monkey-patch the server's ``tool()`` method to auto-wrap handlers."""
        self._original_tool = self._server.tool

        @functools.wraps(self._original_tool)
        def guarded_tool_registration(*args: Any, **kwargs: Any) -> Any:
            decorator = self._original_tool(*args, **kwargs)

            def wrap_handler(func: Callable) -> Any:
                return decorator(
                    guarded_tool(
                        name=kwargs.get("name", func.__name__),
                        pipeline=self._pipeline,
                        rules=self._rules,
                        **self._guard_kwargs,
                    )(func)
                )

            return wrap_handler

        self._server.tool = guarded_tool_registration

    def uninstall(self) -> None:
        """Restore the original ``tool()`` method."""
        if self._original_tool is not None:
            self._server.tool = self._original_tool
            self._original_tool = None


# ── internal helpers ─────────────────────────────────────────────


def _build_tool_call(name: str, args: tuple, kwargs: dict) -> dict:
    """Build a cascade-compatible tool-call dict from handler arguments."""
    return {
        "id": f"mcp_{name}",
        "name": name,
        "arguments": {**{f"arg_{i}": a for i, a in enumerate(args)}, **kwargs},
        "confidence": 1.0,
    }
