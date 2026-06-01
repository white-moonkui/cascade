"""Anthropic Claude adapter — govern tool calls in ``messages.create``.

Entry-points
------------
``guard_anthropic_response`` — post-process an Anthropic ``Message``.
``wrap_anthropic_client`` — monkey-patches ``Anthropic`` for auto-governance.

Usage
-----
.. code-block:: python

   from anthropic import Anthropic
   from cascade import DecisionPipeline
   from cascade.adapters.anthropic import wrap_anthropic_client

   pipe = DecisionPipeline(rules=[{"field": "name", "op": "nin", "value": ["danger"]}])
   client = wrap_anthropic_client(Anthropic(), pipeline=pipe)

   resp = client.messages.create(model="claude-3-5-sonnet", max_tokens=512, messages=[...], tools=[...])
   # ToolUseBlock items are now filtered by cascade governance.
"""

from __future__ import annotations

import functools
from typing import Any

from cascade import DecisionPipeline
from cascade.adapters._base import GuardResult


def guard_anthropic_response(
    message: Any,
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    on_blocked: str = "error",
    **guard_kwargs: Any,
) -> Any:
    """Post-process an Anthropic ``Message`` through cascade.

    Parameters
    ----------
    message:
        The object returned by ``client.messages.create()``.
    pipeline:
        A configured ``DecisionPipeline`` instance.
    rules:
        Rule list forwarded to ``pipeline.guard()``.
    on_blocked:
        ``"error"`` → raise ``RuntimeError`` when all tools blocked.
        ``"skip"`` → remove ``tool_use`` blocks silently.
    """
    content = getattr(message, "content", [])
    tool_blocks = _extract_tool_blocks(content)
    if not tool_blocks:
        return message

    calls = _blocks_to_calls(tool_blocks)
    result = GuardResult(pipeline.guard(tool_calls=calls, rules=rules or [], **guard_kwargs))

    if result.all_blocked:
        if on_blocked == "error":
            raise RuntimeError(
                f"All tool calls were blocked by cascade policy. Audit ID: {result.audit_id}"
            )
        message.content = [b for b in content if _is_not_tool_use(b)]
        return message

    allowed = result.allowed_ids
    message.content = [b for b in content if _is_not_tool_use(b) or getattr(b, "id", None) in allowed]
    return message


def wrap_anthropic_client(
    client: Any,
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    on_blocked: str = "error",
    **guard_kwargs: Any,
) -> Any:
    """Wrap an ``Anthropic`` client so every ``messages.create`` is governed.

    Returns the same *client* object (mutated in-place).
    """
    original_create = client.messages.create

    @functools.wraps(original_create)
    def guarded_create(*args: Any, **kwargs: Any) -> Any:
        resp = original_create(*args, **kwargs)
        return guard_anthropic_response(
            resp, pipeline=pipeline, rules=rules, on_blocked=on_blocked, **guard_kwargs,
        )

    client.messages.create = guarded_create
    return client


# ── internal helpers ─────────────────────────────────────────────


def _extract_tool_blocks(content: list) -> list:
    """Extract ``ToolUseBlock`` items from Anthropic content list."""
    return [b for b in (content or []) if getattr(b, "type", None) == "tool_use"]


def _is_not_tool_use(block: Any) -> bool:
    return getattr(block, "type", None) != "tool_use"


def _blocks_to_calls(blocks: list) -> list[dict]:
    """Convert Anthropic ``ToolUseBlock`` → cascade dicts."""
    return [
        {
            "id": b.id,
            "name": b.name,
            "arguments": getattr(b, "input", {}),
            "confidence": 1.0,
        }
        for b in blocks
    ]
