"""AutoGen adapter — govern tool calls in agent replies.

Entry-points
------------
``guard_agent_reply`` — post-process an AutoGen agent's reply messages.
``wrap_agent`` — wraps an AutoGen ``ConversableAgent`` for auto-governance.

Usage
-----
.. code-block:: python

   from autogen import ConversableAgent
   from cascade import DecisionPipeline
   from cascade.adapters.autogen import wrap_agent

   pipe = DecisionPipeline(rules=[{"field": "name", "op": "nin", "value": ["danger"]}])
   agent = wrap_agent(
       ConversableAgent(name="assistant", llm_config={...}),
       pipeline=pipe,
   )
   # The agent's tool-call messages are now filtered by cascade governance.

Notes
-----
AutoGen represents tool calls as ``tool_calls`` fields on assistant
messages (dicts with ``function`` → ``name`` / ``arguments``).  This
adapter post-processes ``generate_reply()`` output to filter blocked
tool calls before they reach the tool-execution step.

This adapter does NOT wrap the tool-execution side — it only governs
which tool calls the agent is allowed to *propose*.
"""

from __future__ import annotations

import functools
import json
from typing import Any

from cascade import DecisionPipeline
from cascade.adapters._base import GuardResult


def guard_agent_reply(
    reply_messages: list[dict],
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    on_blocked: str = "error",
    **guard_kwargs: Any,
) -> list[dict]:
    """Post-process an AutoGen agent's reply messages through cascade.

    Parameters
    ----------
    reply_messages:
        List of message dicts returned by ``agent.generate_reply()``.
    pipeline:
        A configured ``DecisionPipeline`` instance.
    rules:
        Rule list forwarded to ``pipeline.guard()``.
    on_blocked:
        ``"error"`` → raise ``RuntimeError`` when all tools blocked.
        ``"skip"`` → remove ``tool_calls`` from messages silently.
    **guard_kwargs:
        Extra keyword args passed to ``pipeline.guard()``.

    Returns
    -------
    The modified message list (same length, but with filtered
    ``tool_calls`` entries).
    """
    if not reply_messages:
        return reply_messages

    for msg in reply_messages:
        tool_calls = msg.get("tool_calls", [])
        if not tool_calls:
            continue

        calls = _tool_calls_to_dicts(tool_calls)
        result = GuardResult(pipeline.guard(
            tool_calls=calls, rules=rules or [], **guard_kwargs,
        ))

        if result.all_blocked:
            if on_blocked == "error":
                raise RuntimeError(
                    f"All tool calls were blocked by cascade policy. "
                    f"Audit ID: {result.audit_id}"
                )
            # on_blocked == "skip": remove all tool_calls
            if "function_call" in msg:
                del msg["function_call"]
            msg["tool_calls"] = []
            continue

        allowed = result.allowed_ids
        msg["tool_calls"] = [tc for tc in tool_calls if tc.get("id", "") in allowed]

    return reply_messages


def wrap_agent(
    agent: Any,
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    on_blocked: str = "error",
    **guard_kwargs: Any,
) -> Any:
    """Wrap an AutoGen ``ConversableAgent`` so every ``generate_reply``
    is automatically governed.

    Returns the same *agent* object (mutated in-place).
    """
    original_reply = agent.generate_reply

    @functools.wraps(original_reply)
    def guarded_reply(*args: Any, **kwargs: Any) -> Any:
        reply = original_reply(*args, **kwargs)
        if isinstance(reply, list):
            return guard_agent_reply(
                reply, pipeline=pipeline, rules=rules,
                on_blocked=on_blocked, **guard_kwargs,
            )
        return reply

    agent.generate_reply = guarded_reply
    return agent


# ── internal helpers ─────────────────────────────────────────────


def _tool_calls_to_dicts(tool_calls: list[dict]) -> list[dict]:
    """Convert AutoGen tool_calls entries to cascade dicts.

    AutoGen tool call format::

        {"id": "call_xxx", "function": {"name": "search", "arguments": "{\\"q\\": \\"hello\\"}"}}
    """
    return [
        {
            "id": tc.get("id", f"autogen_{i}"),
            "name": tc.get("function", {}).get("name", "unknown"),
            "arguments": _parse_args(tc.get("function", {}).get("arguments", "{}")),
            "confidence": 1.0,
        }
        for i, tc in enumerate(tool_calls)
    ]


def _parse_args(raw: str) -> dict:
    """Safely parse a JSON string into a dict."""
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
