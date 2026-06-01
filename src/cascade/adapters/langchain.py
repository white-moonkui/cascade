"""LangChain adapter — govern tool calls produced by agents.

Entry-point
-----------
``guard_agent_output`` — pure post-processor for ``AIMessage`` or
agent result dicts.  Zero side-effects, zero LangChain version coupling.

Usage
-----
.. code-block:: python

   from langchain.agents import AgentExecutor
   from cascade import DecisionPipeline
   from cascade.adapters.langchain import guard_agent_output

   pipe = DecisionPipeline(rules=[{"field": "name", "op": "nin", "value": ["danger"]}])

   result = agent_executor.invoke({"input": query})
   result = guard_agent_output(result, pipeline=pipe)

   # result["output"] now only contains allowed tool calls
"""

from __future__ import annotations

from typing import Any

from cascade import DecisionPipeline
from cascade.adapters._base import GuardResult


def guard_agent_output(
    agent_output: dict[str, Any] | Any,
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    **guard_kwargs: Any,
) -> dict[str, Any] | Any:
    """Post-process a LangChain agent's output through cascade.

    Handles two common output shapes:

    * ``dict`` with ``"output"`` key (``AgentExecutor.invoke()`` return).
    * ``AIMessage``-like object with ``.tool_calls`` / ``.response_metadata``.

    When tool calls are blocked the message content is patched with a
    governance notice so the LLM can self-correct on the next turn.

    Parameters
    ----------
    agent_output:
        The return value of ``agent_executor.invoke()`` or an ``AIMessage``.
    pipeline:
        A configured ``DecisionPipeline`` instance.
    rules:
        Rule list forwarded to ``pipeline.guard()``.
    **guard_kwargs:
        Extra keyword args passed to ``pipeline.guard()``.

    Returns
    -------
    The same type as *agent_output* with tool calls filtered.
    """
    # Dict shape from AgentExecutor
    if isinstance(agent_output, dict):
        output = agent_output.get("output", "")
        if hasattr(output, "tool_calls") and output.tool_calls:
            _govern_message(output, pipeline, rules or [], guard_kwargs)
        return agent_output

    # AIMessage-like object
    if hasattr(agent_output, "tool_calls") and agent_output.tool_calls:
        _govern_message(agent_output, pipeline, rules or [], guard_kwargs)

    return agent_output


# ── internal ─────────────────────────────────────────────────────


def _govern_message(
    message: Any,
    pipeline: DecisionPipeline,
    rules: list[dict],
    guard_kwargs: dict,
) -> None:
    """Filter tool calls on an AIMessage-like object in place."""
    calls = _extract(message.tool_calls)
    if not calls:
        return

    result = GuardResult(pipeline.guard(tool_calls=calls, rules=rules, **guard_kwargs))

    if result.all_blocked:
        message.tool_calls = []
        _patch_content(message, "All tool calls were blocked by cascade policy.")
        return

    allowed = result.allowed_ids
    message.tool_calls = [tc for tc in message.tool_calls if tc.get("id") in allowed]
    if not message.tool_calls:
        _patch_content(message, "All tool calls were blocked by cascade policy.")


def _extract(tool_calls: list[Any]) -> list[dict]:
    """Convert LangChain tool-call entries into cascade dicts.

    LangChain 0.3+ uses ``{"name": …, "args": …, "id": …}`` format.
    """
    return [
        {
            "id": tc.get("id", f"lc_{i}"),
            "name": tc["name"],
            "arguments": tc.get("args", {}),
        }
        for i, tc in enumerate(tool_calls)
    ]


def _patch_content(message: Any, text: str) -> None:
    """Append governance notice to message content."""
    existing = message.content or ""
    message.content = (existing + "\n\n" + text).strip()
