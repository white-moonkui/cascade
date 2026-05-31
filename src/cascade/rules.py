"""Rule factory functions for common governance patterns.

Every function returns a **rule dict** or a **composite rule dict** that
``DecisionPipeline.guard()`` can consume directly.

Usage::

    from cascade.rules import high_confidence, safe_tools, require_role, all_of

    pipe.guard(
        tool_calls=[...],
        rules=[
            all_of(
                high_confidence(0.7),
                safe_tools(),
                require_role("admin"),
            ),
        ],
    )
"""
# ---------------------------------------------------------------------------
# Leaf rules  ─  each returns ``{"field": …, "op": …, "value": …}``
# ---------------------------------------------------------------------------


def high_confidence(min_: float = 0.5) -> dict:
    """Only allow tool calls whose ``confidence >= min_``."""
    return {"field": "confidence", "op": "gte", "value": min_}


def safe_tools(block: list[str] | None = None) -> dict:
    """Block dangerous tool names.

    Default block-list: ``delete``, ``exec``, ``rm``, ``drop``, ``shutdown``.
    """
    blocked = block or ["delete", "exec", "rm", "drop", "shutdown"]
    return {"field": "name", "op": "nin", "value": blocked}


def allow_only(*names: str) -> dict:
    """Allow *only* the named tools (everything else is rejected)."""
    return {"field": "name", "op": "in", "value": list(names)}


def block_only(*names: str) -> dict:
    """Block specific tools while allowing everything else."""
    return {"field": "name", "op": "nin", "value": list(names)}


def require_role(role: str, field: str = "user_role") -> dict:
    """Require a specific role in the session context."""
    return {"field": field, "op": "eq", "value": role}


def field_matches(field: str, op: str, value) -> dict:
    """Generic field‑level rule — any operator, any value."""
    return {"field": field, "op": op, "value": value}


def argument_matches(arg_path: str, op: str, value) -> dict:
    """Check a nested argument field (e.g. ``arguments.path``)."""
    return {"field": f"arguments.{arg_path}", "op": op, "value": value}


def rate_limit(max_calls: int, per_seconds: float = 60.0) -> dict:
    """Rate‑limit a tool at the session level.

    .. note::
       This rule must be checked against the **context** dict, not a tool
       call.  Pass accumulated call timestamps as ``context["_call_times"]``.
    """
    return {"field": "_call_times", "op": "rate", "value": {"max": max_calls, "window": per_seconds}}


# ---------------------------------------------------------------------------
# Composite rules  ─  each returns ``{"compose": …, …}``
# ---------------------------------------------------------------------------


def all_of(*rules: dict) -> dict:
    """AND — every sub‑rule must pass."""
    return {"compose": "all_of", "rules": list(rules)}


def any_of(*rules: dict) -> dict:
    """OR — at least one sub‑rule must pass."""
    return {"compose": "any_of", "rules": list(rules)}


def not_(rule: dict) -> dict:
    """NOT — negate a single rule."""
    return {"compose": "not", "rule": rule}
