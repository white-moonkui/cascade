"""Action handlers for rejected tool calls.

Actions let you respond when a tool call fails governance — block it,
transform its arguments, or redirect to a safer tool.

Usage::

    from cascade.actions import block, redirect

    pipe.guard(
        tool_calls=[...],
        rules=[...],
        actions={
            "delete_file": redirect("safe_delete"),
            "shell_exec": block("Shell access denied"),
        },
    )
"""

from __future__ import annotations
from typing import Any, Callable


def block(reason: str = "Blocked by policy") -> dict:
    """Reject the tool call with a reason."""
    return {"action": "block", "reason": reason}


def redirect(to_tool: str, transform_args: Callable[[dict], dict] | None = None) -> dict:
    """Redirect a rejected tool call to a safer tool.

    The original ``arguments`` are passed through *transform_args* if
    provided, otherwise forwarded as-is.
    """
    if transform_args is None:

        def _passthrough(args: dict) -> dict:
            return args

        transform_args = _passthrough
    return {"action": "redirect", "to_tool": to_tool, "transform_args": transform_args}


def transform(fn: Callable[[dict], dict | None]) -> dict:
    """Rewrite a rejected tool call.

    The callable receives the original tool-call dict and must return a
    modified dict, or ``None`` to discard the tool call entirely.
    """
    return {"action": "transform", "fn": fn}
