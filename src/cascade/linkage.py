"""
C₃–C₄ linkage — connects selection pressure with feedback.

Feeds outcome rewards back into the pipeline to adjust future
selection pressure. Uses ``Store`` for checkpointing.
"""

from __future__ import annotations

from typing import Any, Optional

from cascade._store import Store
from cascade.c3_selector import Candidate, SelectionPressure
from cascade.c4_feedback import FeedbackLoop


class Linkage:
    """
    Bridges C₃ (selection) and C₄ (feedback).

    After a decision outcome is recorded in C₄, ``adjust_pressure``
    applies the reward delta to the relevant candidate's score in C₃,
    creating a closed learning loop.
    """

    def __init__(self, selector: Optional[SelectionPressure] = None, feedback: Optional[FeedbackLoop] = None, store: Optional[Store] = None):
        self._store = store or Store()
        self._selector = selector or SelectionPressure(store=self._store)
        self._feedback = feedback or FeedbackLoop(store=self._store)

    # -- core loop -----------------------------------------------------

    def adjust_pressure(self, candidate: Candidate, outcome_reward: float, learning_rate: float = 0.1) -> Candidate:
        """
        Adjust a candidate's score based on an outcome reward.

        ``new_score = score + learning_rate * reward``
        """
        candidate.score += learning_rate * outcome_reward
        candidate.metadata["last_adjustment"] = outcome_reward
        candidate.metadata["adjusted_at"] = __import__("datetime").datetime.now().isoformat()
        return candidate

    def run_cycle(
        self,
        candidates: list[Candidate],
        top_k: int = 1,
        strategy: str = "softmax",
        **kwargs,
    ) -> dict:
        """
        Run one complete C₃→C₄ cycle.

        1. Rank candidates via ``SelectionPressure.rank``.
        2. Select top-*k* candidates.
        3. Return results (selection step only — feedback requires
           external outcome data via ``record_outcome``).

        Returns a dict with keys:
        ``ranked``, ``selected``, ``strategy``, ``top_k``.
        """
        ranked = self._selector.rank(candidates, strategy=strategy, **kwargs)
        selected = self._selector.select(ranked, top_k=top_k)
        tag = kwargs.get("tag", "default")
        self._selector.save_state(tag, ranked)
        return {
            "ranked": ranked,
            "selected": selected,
            "strategy": strategy,
            "top_k": top_k,
        }

    def record_outcome(
        self,
        decision_id: str,
        expected: Any,
        actual: Any,
        candidates: Optional[list[Candidate]] = None,
        strategy: str = "binary",
        learning_rate: float = 0.1,
        **kwargs,
    ) -> dict:
        """
        Record an outcome in C₄ and adjust the matching candidate's
        score in C₃.

        If *candidates* is provided, the candidate whose ``id``
        matches *decision_id* will have its pressure adjusted.
        """
        outcome = self._feedback.record(decision_id, expected, actual, strategy=strategy, **kwargs)
        result = {
            "outcome": outcome,
            "adjusted_candidates": [],
        }
        if candidates:
            for c in candidates:
                if c.id == decision_id:
                    self.adjust_pressure(c, outcome.reward, learning_rate=learning_rate)
                    result["adjusted_candidates"].append(c)
        return result

    # -- checkpointing -------------------------------------------------

    def save_cycle(self, tag: str, state: dict) -> bool:
        state["_linkage_tag"] = tag
        return self._store.save(f"linkage_{tag}", state)

    def load_cycle(self, tag: str) -> Optional[dict]:
        return self._store.load(f"linkage_{tag}")
