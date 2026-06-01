"""
C₃ — Selection Pressure Engine.

Applies configurable pressure strategies to rank and select among
competing decision candidates. Uses ``Store`` for checkpointing.
"""

from __future__ import annotations

import math
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
    - ``ucb1``: Upper Confidence Bound — balances exploration vs.
      exploitation via ``score + exploration_weight * sqrt(2 * ln(N) / n)``.
      Requires that ``record_selection()`` is called after each round
      so play-counts are up to date.
    """

    STRATEGIES = ("uniform", "linear", "softmax", "threshold", "ucb1")

    def __init__(self, store: Optional[Store] = None):
        self._store = store or Store()
        self._counts: dict[str, int] = {}
        self._load_counts()

    # -- public API ---------------------------------------------------

    def rank(self, candidates: list[Candidate], strategy: str = "softmax", **kwargs) -> list[Candidate]:
        """
        Rank candidates by applying the selected pressure strategy.

        Parameters
        ----------
        candidates:
            List of ``Candidate`` objects.
        strategy:
            One of ``uniform``, ``linear``, ``softmax``, ``threshold``,
            ``ucb1``.
        **kwargs:
            ``min_score`` (for ``threshold``), ``temperature`` (for
            ``softmax``), ``exploration_weight`` (for ``ucb1``).

        Returns candidates sorted descending by pressure.
        """
        if not candidates:
            return []
        strategy_fn = getattr(self, f"_strategy_{strategy}", None)
        if strategy_fn is None:
            raise ValueError(f"Unknown pressure strategy: {strategy}. Choose from {self.STRATEGIES}")

        scores = [c.score for c in candidates]
        pressures = strategy_fn(scores, candidates=candidates, **kwargs)
        for c, p in zip(candidates, pressures):
            c.pressure = round(p, 6)
        candidates.sort(key=lambda c: c.pressure, reverse=True)
        return candidates

    def select(self, candidates: list[Candidate], top_k: int = 1) -> list[Candidate]:
        """Return the top-*k* candidates by pressure."""
        ranked = sorted(candidates, key=lambda c: c.pressure, reverse=True)
        return ranked[:top_k]

    def record_selection(self, selected: list[Candidate]) -> None:
        """Increment play-counts for each selected candidate and persist."""
        for c in selected:
            self._counts[c.label] = self._counts.get(c.label, 0) + 1
        self._save_counts()

    def selection_counts(self) -> dict[str, int]:
        """Return a copy of the current play-counts per candidate label."""
        return dict(self._counts)

    def reset_counts(self, label: Optional[str] = None) -> int:
        """Reset play-counts. If *label* is given, reset only that label.
        Returns the number of entries cleared."""
        if label:
            n = 1 if label in self._counts else 0
            self._counts.pop(label, None)
        else:
            n = len(self._counts)
            self._counts.clear()
        self._save_counts()
        return n

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
        scaled = [s / temperature for s in scores]
        exps = [math.exp(s - max(scaled)) for s in scaled]  # numeric stability
        total = sum(exps)
        return [e / total for e in exps]

    @staticmethod
    def _strategy_threshold(scores: list[float], min_score: float = 0.5, **kwargs) -> list[float]:
        return [1.0 if s >= min_score else 0.0 for s in scores]

    def _strategy_ucb1(
        self,
        scores: list[float],
        exploration_weight: float = 1.0,
        candidates: Optional[list[Candidate]] = None,
        **kwargs,
    ) -> list[float]:
        """Upper Confidence Bound (UCB1) — score + exploration bonus.

        The exploration bonus is ``sqrt(2 * ln(N) / n)`` where *N* is the
        total selections across all candidates and *n* is the per-candidate
        play-count.  Unseen candidates (n == 0) receive a large bonus
        to encourage initial exploration.
        """
        if not candidates:
            return list(scores)

        total = sum(self._counts.values())
        results: list[float] = []
        for c, s in zip(candidates, scores):
            n = self._counts.get(c.label, 0)
            if n == 0:
                bonus = exploration_weight * 1e6  # encourage initial exploration
            else:
                bonus = exploration_weight * math.sqrt(2.0 * math.log(total + 1) / n)
            results.append(s + bonus)
        return results

    # -- adaptive threshold -------------------------------------------

    @staticmethod
    def adaptive_threshold(
        avg_reward: float = 0.0,
        min_threshold: float = 0.3,
        max_threshold: float = 0.9,
        sensitivity: float = 0.3,
    ) -> float:
        """Compute a dynamic ``min_score`` threshold from feedback signals.

        When the system is performing well (high avg_reward), we can afford
        to be stricter (higher threshold).  When performance is poor, we
        lower the bar to allow more exploration.

        ``threshold = clamp(min_threshold + sensitivity * avg_reward, min_threshold, max_threshold)``

        Parameters
        ----------
        avg_reward:
            Average reward from the feedback loop (typically -1..1 range).
        min_threshold:
            Floor for the computed threshold (default 0.3).
        max_threshold:
            Ceiling for the computed threshold (default 0.9).
        sensitivity:
            How strongly avg_reward influences the threshold (default 0.3).
        """
        raw = min_threshold + sensitivity * avg_reward
        return max(min_threshold, min(max_threshold, raw))

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

    # -- play-count persistence ---------------------------------------

    def _counts_key(self) -> str:
        return "_c3_selection_counts"

    def _save_counts(self) -> None:
        self._store.save(self._counts_key(), dict(self._counts))

    def _load_counts(self) -> None:
        data = self._store.load(self._counts_key())
        if data is not None and isinstance(data, dict):
            self._counts = {}
            for k, v in data.items():
                if k == "_saved_at":
                    continue
                try:
                    self._counts[str(k)] = int(v)
                except (ValueError, TypeError):
                    continue
        else:
            self._counts = {}
