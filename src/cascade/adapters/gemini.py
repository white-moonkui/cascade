"""Google Gemini adapter — govern tool calls in ``client.models.generate_content``.

Entry-points
------------
``guard_gemini_response`` — post-process a Gemini ``GenerateContentResponse``.
``wrap_genai_client`` — monkey-patches ``genai.Client`` for auto-governance.

Usage
-----
.. code-block:: python

   from google import genai
   from cascade import DecisionPipeline
   from cascade.adapters.gemini import wrap_genai_client

   pipe = DecisionPipeline(rules=[{"field": "name", "op": "nin", "value": ["danger"]}])
   client = wrap_genai_client(genai.Client(api_key="..."), pipeline=pipe)

   resp = client.models.generate_content(model="gemini-2.0-flash", contents="search papers")
   # function_calls are now filtered by cascade governance.

Notes
-----
The Google GenAI SDK (``google-genai``) represents tool calls as
``FunctionCall`` objects on ``response.candidates[0].content.parts``.
Each ``FunctionCall`` has ``name`` and ``args`` attributes.
"""

from __future__ import annotations

import functools
from typing import Any

from cascade import DecisionPipeline
from cascade.adapters._base import GuardResult


def guard_gemini_response(
    response: Any,
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    on_blocked: str = "error",
    **guard_kwargs: Any,
) -> Any:
    """Post-process a Gemini ``GenerateContentResponse`` through cascade.

    Parameters
    ----------
    response:
        The object returned by ``client.models.generate_content()``.
    pipeline:
        A configured ``DecisionPipeline`` instance.
    rules:
        Rule list forwarded to ``pipeline.guard()``.  Falls back to
        the pipeline's ``gate.rules`` if omitted.
    on_blocked:
        ``"error"`` → raise ``RuntimeError`` when all tools are blocked.
        ``"skip"`` → remove function calls silently.
    **guard_kwargs:
        Extra keyword args passed to ``pipeline.guard()``.

    Returns
    -------
    The modified ``GenerateContentResponse`` (same type as *response*).
    """
    candidates = getattr(response, "candidates", [])
    if not candidates:
        return response

    for candidate in candidates:
        _govern_candidate(candidate, pipeline, rules or [], on_blocked, guard_kwargs)

    return response


def wrap_genai_client(
    client: Any,
    pipeline: DecisionPipeline,
    rules: list[dict] | None = None,
    on_blocked: str = "error",
    **guard_kwargs: Any,
) -> Any:
    """Wrap a ``genai.Client`` so every ``models.generate_content``
    is automatically governed.

    Returns the same *client* object (mutated in-place for
    monkey-patch compatibility).
    """
    original_generate = client.models.generate_content

    @functools.wraps(original_generate)
    def guarded_generate(*args: Any, **kwargs: Any) -> Any:
        resp = original_generate(*args, **kwargs)
        return guard_gemini_response(
            resp,
            pipeline=pipeline,
            rules=rules,
            on_blocked=on_blocked,
            **guard_kwargs,
        )

    client.models.generate_content = guarded_generate
    return client


# ── internal helpers ─────────────────────────────────────────────


def _govern_candidate(
    candidate: Any,
    pipeline: DecisionPipeline,
    rules: list[dict],
    on_blocked: str,
    guard_kwargs: dict,
) -> None:
    """Apply cascade to a single ``Candidate`` — mutates parts in place."""
    content = getattr(candidate, "content", None)
    if content is None:
        return
    parts = getattr(content, "parts", [])
    if not parts:
        return

    function_calls = _extract_function_calls(parts)
    if not function_calls:
        return

    calls = _calls_to_dicts(function_calls)
    result = GuardResult(pipeline.guard(tool_calls=calls, rules=rules, **guard_kwargs))

    if result.all_blocked:
        if on_blocked == "error":
            raise RuntimeError(
                f"All tool calls were blocked by cascade policy. Audit ID: {result.audit_id}"
            )
        # on_blocked == "skip": remove all function_call parts
        candidate.content.parts = [p for p in parts if not _is_function_call(p)]
        return

    allowed_names = {c["name"] for c in result.allowed}
    # Keep only allowed function-call parts; preserve text/other parts
    candidate.content.parts = [
        p for p in parts
        if not _is_function_call(p) or getattr(p.function_call, "name", None) in allowed_names
    ]


def _is_function_call(part: Any) -> bool:
    """Check if a ``Part`` contains a function call."""
    fc = getattr(part, "function_call", None)
    return fc is not None


def _extract_function_calls(parts: list[Any]) -> list[Any]:
    """Extract non-None ``FunctionCall`` objects from content parts."""
    return [p.function_call for p in parts if _is_function_call(p)]


def _calls_to_dicts(function_calls: list[Any]) -> list[dict]:
    """Convert Gemini ``FunctionCall`` objects → cascade dicts."""
    return [
        {
            "id": getattr(fc, "id", f"gemini_{i}"),
            "name": fc.name,
            "arguments": dict(fc.args) if hasattr(fc, "args") and fc.args else {},
            "confidence": 1.0,
        }
        for i, fc in enumerate(function_calls)
    ]
