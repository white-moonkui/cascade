"""
C₄ — Feedback Loop.

Tracks outcome signals for previously selected decisions, computes
reward / penalty deltas, and feeds corrections back into the
pipeline. Uses ``Store`` for checkpointing.
"""

from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from cascade._store import Store


@dataclass
class Outcome:
    """Record of a single decision outcome."""

    decision_id: str
    expected: Any
    actual: Any
    reward: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)


class FeedbackLoop:
    """
    Tracks decision outcomes and computes reward/penalty deltas.

    Strategies
    ----------
    - ``binary``: +1 for match, -1 for mismatch.
    - ``proportional``: reward scales with outcome magnitude.
    - ``threshold``: +1 if actual within tolerance of expected.
    """

    STRATEGIES = ("binary", "proportional", "threshold")

    def __init__(self, store: Optional[Store] = None):
        self._store = store or Store()
        self._history: list[Outcome] = []
        self._load_history()

    # -- outcome recording --------------------------------------------

    def record(self, decision_id: str, expected: Any, actual: Any, strategy: str = "binary", **kwargs) -> Outcome:
        reward = self._compute_reward(expected, actual, strategy, **kwargs)
        outcome = Outcome(
            decision_id=decision_id,
            expected=expected,
            actual=actual,
            reward=reward,
        )
        self._history.append(outcome)
        self._save_history()
        return outcome

    def _compute_reward(self, expected: Any, actual: Any, strategy: str, **kwargs) -> float:
        if strategy == "binary":
            return 1.0 if actual == expected else -1.0
        elif strategy == "proportional":
            try:
                return float(actual) - float(expected)
            except (TypeError, ValueError):
                return 0.0
        elif strategy == "threshold":
            tolerance = kwargs.get("tolerance", 0.1)
            try:
                return 1.0 if abs(float(actual) - float(expected)) <= tolerance else -1.0
            except (TypeError, ValueError):
                return 0.0
        else:
            raise ValueError(f"Unknown feedback strategy: {strategy}")

    # -- history queries ----------------------------------------------

    def recent(self, n: int = 10) -> list[Outcome]:
        return self._history[-n:]

    def average_reward(self, last_n: Optional[int] = None) -> float:
        entries = self._history[-last_n:] if last_n else self._history
        if not entries:
            return 0.0
        return sum(o.reward for o in entries) / len(entries)

    def summary(self) -> dict:
        return {
            "module": "C4 (Feedback)",
            "total_outcomes": len(self._history),
            "avg_reward": self.average_reward(),
            "recent": [
                {
                    "decision_id": o.decision_id,
                    "expected": o.expected,
                    "actual": o.actual,
                    "reward": o.reward,
                    "timestamp": o.timestamp,
                }
                for o in self.recent(5)
            ],
        }

    # -- persistence ---------------------------------------------------

    def _history_path(self):
        return self._store.store_dir / "feedback_history.json"

    def _save_history(self):
        data = [
            {
                "decision_id": o.decision_id,
                "expected": o.expected,
                "actual": o.actual,
                "reward": o.reward,
                "timestamp": o.timestamp,
                "metadata": o.metadata,
            }
            for o in self._history
        ]
        import json

        with open(self._history_path(), "w") as f:
            json.dump(data, f, default=str, indent=2)

    def _load_history(self):
        path = self._history_path()
        if not path.exists():
            return
        import json

        with open(path) as f:
            data = json.load(f)
        for entry in data:
            self._history.append(
                Outcome(
                    decision_id=entry["decision_id"],
                    expected=entry["expected"],
                    actual=entry["actual"],
                    reward=entry.get("reward", 0.0),
                    timestamp=entry.get("timestamp", ""),
                    metadata=entry.get("metadata", {}),
                )
            )
