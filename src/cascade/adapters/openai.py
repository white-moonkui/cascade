"""OpenAI SDK adapter — govern tool calls in ``client.chat.completions.create``.

Two entry-points
------------------------
``guard_openai_response`` — pure post-processor, no side-effects.
``wrap_openai_client`` — monkey-patches an ``OpenAI`` client for auto-governance.

Usage
-----
.. code-block:: python

   from openai import OpenAI
   from cascade import DecisionPipeline
   from cascade.adapters.openai import wrap_openai_client

   pipe = DecisionPipeline(rules=[{"field": "name", "op": "nin", "value": ["rm"]}])
   client = wrap_openai_client(OpenAI(), pipeline=pipe)

   resp = client.chat.completions.create(model="gpt-4", messages=[...], tools=[...])
   # resp.choices[0].message.tool_calls now only contains allowed tools
"""

from __future__ import annotations

import functools
import json
from typing import Any, Callable

from cascade import DecisionPipeline
from cascade.adapters._base import GuardResult


def guard_openai_response(
    response: Any,
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    on_blocked: str = "error",
    **guard_kwargs: Any,
) -> Any:
    """Post-process an OpenAI ``ChatCompletion`` response through cascade.

    Parameters
    ----------
    response:
        The object returned by ``client.chat.completions.create()``.
    pipeline:
        A configured ``DecisionPipeline`` instance.
    rules:
        Rule list forwarded to ``pipeline.guard()``.  Falls back to
        the pipeline's ``gate.rules`` if omitted.
    on_blocked:
        ``"error"`` → raise ``RuntimeError`` when all tools are blocked.
        ``"skip"`` → remove all tool calls, set ``finish_reason="stop"``.
    **guard_kwargs:
        Extra keyword args passed to ``pipeline.guard()`` (e.g.
        *strategy*, *top_k*, *actions*).

    Returns
    -------
    The modified ``ChatCompletion`` (same type as *response*).
    """
    try:
        choices = response.choices
    except AttributeError:
        msg = (
            "Expected an OpenAI ChatCompletion response object. "
            "Got {tp} — did you pass the right object?"
        )
        raise TypeError(msg.format(tp=type(response).__name__))

    for choice in choices:
        _govern_choice(choice, pipeline, rules or [], on_blocked, guard_kwargs)

    return response


def wrap_openai_client(
    client: Any,
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    on_blocked: str = "error",
    **guard_kwargs: Any,
) -> Any:
    """Wrap an ``OpenAI`` client so every ``chat.completions.create``
    is automatically governed.

    Returns the same *client* object (mutated in-place for
    monkey-patch compatibility).
    """
    original_create = client.chat.completions.create

    @functools.wraps(original_create)
    def guarded_create(*args: Any, **kwargs: Any) -> Any:
        resp = original_create(*args, **kwargs)
        return guard_openai_response(
            resp,
            pipeline=pipeline,
            rules=rules,
            on_blocked=on_blocked,
            **guard_kwargs,
        )

    client.chat.completions.create = guarded_create
    return client


# ── internal helpers ─────────────────────────────────────────────

_RESPONSE_MSG = (
    "Tool call `{name}` was blocked by cascade policy. "
    "Audit ID: {audit_id}"
)


def _govern_choice(
    choice: Any,
    pipeline: DecisionPipeline,
    rules: list[dict],
    on_blocked: str,
    guard_kwargs: dict,
) -> None:
    """Apply cascade to a single ``Choice`` — mutates *choice* in place."""
    if choice.finish_reason != "tool_calls":
        return
    raw_tool_calls = choice.message.tool_calls
    if not raw_tool_calls:
        return

    calls = _extract_tool_calls(raw_tool_calls)
    result = GuardResult(pipeline.guard(tool_calls=calls, rules=rules, **guard_kwargs))

    if result.all_blocked:
        if on_blocked == "error":
            raise RuntimeError(
                _RESPONSE_MSG.format(
                    name=(
                        calls[0]["name"] if calls else "unknown"
                    ),
                    audit_id=result.audit_id,
                )
            )
        # on_blocked == "skip"
        choice.message.tool_calls = []
        choice.finish_reason = "stop"
        return

    # Keep only allowed tool calls
    choice.message.tool_calls = [tc for tc in raw_tool_calls if tc.id in result.allowed_ids]
    if not choice.message.tool_calls:
        choice.finish_reason = "stop"


def _extract_tool_calls(raw_tool_calls: list[Any]) -> list[dict]:
    """Convert OpenAI SDK tool-call objects into cascade dicts."""
    return [
        {
            "id": tc.id,
            "name": tc.function.name,
            "arguments": json.loads(tc.function.arguments),
            "confidence": getattr(tc, "confidence", 0.0),
        }
        for tc in raw_tool_calls
    ]
