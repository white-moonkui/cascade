"""
C₃ — Selection Pressure Engine.

Applies configurable pressure strategies to rank and select among
competing decision candidates. Uses ``Store`` for checkpointing.
"""

from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass, field

from cascade._store import Store


@dataclass
class Candidate:
    """A single decision candidate with selection metadata."""

    id: str
    label: str
    score: float = 0.0
    pressure: float = 0.0
    metadata: dict = field(default_factory=dict)


class SelectionPressure:
    """
    Applies configurable pressure strategies to rank candidates.

    Pressure strategies
    -------------------
    - ``uniform``: equal pressure across all candidates.
    - ``linear``: pressure proportional to each candidate's score.
    - ``softmax``: softmax-normalised pressure from scores.
    - ``threshold``: full pressure for candidates above ``min_score``,
      zero for the rest.
    """

    STRATEGIES = ("uniform", "linear", "softmax", "threshold")

    def __init__(self, store: Optional[Store] = None):
        self._store = store or Store()

    def rank(self, candidates: list[Candidate], strategy: str = "softmax", **kwargs) -> list[Candidate]:
        """
        Rank candidates by applying the selected pressure strategy.

        Parameters
        ----------
        candidates:
            List of ``Candidate`` objects.
        strategy:
            One of ``uniform``, ``linear``, ``softmax``, ``threshold``.
        **kwargs:
            ``min_score`` (for ``threshold``), ``temperature`` (for
            ``softmax``).

        Returns candidates sorted descending by pressure.
        """
        if not candidates:
            return []
        strategy_fn = getattr(self, f"_strategy_{strategy}", None)
        if strategy_fn is None:
            raise ValueError(f"Unknown pressure strategy: {strategy}. Choose from {self.STRATEGIES}")

        scores = [c.score for c in candidates]
        pressures = strategy_fn(scores, **kwargs)
        for c, p in zip(candidates, pressures):
            c.pressure = round(p, 6)
        candidates.sort(key=lambda c: c.pressure, reverse=True)
        return candidates

    def select(self, candidates: list[Candidate], top_k: int = 1) -> list[Candidate]:
        """Return the top-*k* candidates by pressure."""
        ranked = sorted(candidates, key=lambda c: c.pressure, reverse=True)
        return ranked[:top_k]

    # -- pressure strategies -------------------------------------------

    @staticmethod
    def _strategy_uniform(scores: list[float], **kwargs) -> list[float]:
        return [1.0 / len(scores)] * len(scores) if scores else []

    @staticmethod
    def _strategy_linear(scores: list[float], **kwargs) -> list[float]:
        total = sum(scores)
        return [s / total for s in scores] if total else [0.0] * len(scores)

    @staticmethod
    def _strategy_softmax(scores: list[float], temperature: float = 1.0, **kwargs) -> list[float]:
        import math

        scaled = [s / temperature for s in scores]
        exps = [math.exp(s - max(scaled)) for s in scaled]  # numeric stability
        total = sum(exps)
        return [e / total for e in exps]

    @staticmethod
    def _strategy_threshold(scores: list[float], min_score: float = 0.5, **kwargs) -> list[float]:
        return [1.0 if s >= min_score else 0.0 for s in scores]

    # -- checkpointing ------------------------------------------------

    def save_state(self, tag: str, candidates: list[Candidate]) -> bool:
        data = {
            "tag": tag,
            "candidates": [
                {"id": c.id, "label": c.label, "score": c.score, "pressure": c.pressure, "metadata": c.metadata}
                for c in candidates
            ],
        }
        return self._store.save(f"c3_{tag}", data)

    def load_state(self, tag: str) -> Optional[list[Candidate]]:
        data = self._store.load(f"c3_{tag}")
        if data is None:
            return None
        return [
            Candidate(
                id=c["id"],
                label=c["label"],
                score=c["score"],
                pressure=c.get("pressure", 0.0),
                metadata=c.get("metadata", {}),
            )
            for c in data.get("candidates", [])
        ]
