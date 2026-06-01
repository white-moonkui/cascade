"""CrewAI adapter — govern tool calls in ``Crew.kickoff()``.

Entry-points
------------
``guard_crew_output`` — post-process a crew's output.
``wrap_crew`` — wraps a ``Crew`` so every ``kickoff()`` is governed.

Usage
-----
.. code-block:: python

   from crewai import Crew, Agent, Task
   from cascade import DecisionPipeline
   from cascade.adapters.crewai import wrap_crew

   pipe = DecisionPipeline(rules=[{"field": "name", "op": "nin", "value": ["danger"]}])
   crew = wrap_crew(
       Crew(agents=[...], tasks=[...]),
       pipeline=pipe,
   )
   result = crew.kickoff()  # tool calls are auto-governed
"""

from __future__ import annotations

import functools
from typing import Any, Optional

from cascade import DecisionPipeline
from cascade.adapters._base import GuardResult

# ═══════════════════════════════════════════════════════════════════
# CrewAI 0.30+ internals (accessed via duck-typing — no hard import)
# ═══════════════════════════════════════════════════════════════════

_TOOL_CALL_ATTRS = ("tool_calls", "tools")


def _extract_tool_calls(output: Any) -> list[dict]:
    """Extract tool-call-like dicts from a CrewAI task output.

    CrewAI delegates to LangChain internally, so outputs may carry
    ``.tool_calls`` (AIMessage) or ``.tools`` (Agent).
    """
    for attr in _TOOL_CALL_ATTRS:
        items = getattr(output, attr, None) or []
        if not items:
            continue
        # LangChain-style dicts with "name"/"args" keys
        if isinstance(items[0], dict) and "name" in items[0]:
            return [
                {"id": tc.get("id", f"ca_{i}"), "name": tc["name"], "arguments": tc.get("args", {})}
                for i, tc in enumerate(items)
            ]
    return []


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════


def guard_crew_output(
    output: Any,
    pipeline: DecisionPipeline,
    rules: Optional[list[dict]] = None,
    **guard_kwargs: Any,
) -> Any:
    """Post-process a CrewAI crew/task output through cascade.

    Handles both the final crew output string and intermediate
    task outputs that carry tool-call metadata.
    """
    calls = _extract_tool_calls(output)
    if not calls:
        return output

    result = GuardResult(pipeline.guard(tool_calls=calls, rules=rules or [], **guard_kwargs))
    if result.all_blocked:
        for attr in _TOOL_CALL_ATTRS:
            if hasattr(output, attr):
                setattr(output, attr, [])
        return output

    allowed = result.allowed_ids
    for attr in _TOOL_CALL_ATTRS:
        items = getattr(output, attr, None) or []
        if items and isinstance(items[0], dict):
            setattr(output, attr, [tc for tc in items if tc.get("id") in allowed or tc.get("name") in allowed])
    return output


def wrap_crew(
    crew: Any,
    pipeline: DecisionPipeline,
    rules: Optional[list[dict]] = None,
    **guard_kwargs: Any,
) -> Any:
    """Wrap a ``Crew`` so every ``kickoff()`` auto-governs tool calls.

    Returns the same *crew* object (mutated in-place).
    """
    original_kickoff = crew.kickoff

    @functools.wraps(original_kickoff)
    def guarded_kickoff(*args: Any, **kwargs: Any) -> Any:
        result = original_kickoff(*args, **kwargs)
        return guard_crew_output(result, pipeline=pipeline, rules=rules, **guard_kwargs)

    crew.kickoff = guarded_kickoff
    return crew
