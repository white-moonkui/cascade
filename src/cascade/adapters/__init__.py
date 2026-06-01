"""
cascade adapters — plug governance into LLM frameworks.

Each adapter is a thin (<80 lines) bridge between ``cascade.guard()``
and a specific SDK.  Zero impact on the core codebase; import only
what you need.
"""

from cascade.adapters._base import ToolCallConverter, GuardResult

__all__ = [
    "ToolCallConverter",
    "GuardResult",
]
