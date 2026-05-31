"""Tests for C₃–C₄ Linkage."""

from cascade.c3_selector import Candidate, SelectionPressure
from cascade.c4_feedback import FeedbackLoop
from cascade.linkage import Linkage


class TestAdjustPressure:
    def test_positive_reward_increases_score(self):
        c = Candidate(id="a", label="A", score=0.5)
        linkage = Linkage()
        linkage.adjust_pressure(c, outcome_reward=1.0, learning_rate=0.1)
        assert c.score == 0.6
        assert c.metadata.get("last_adjustment") == 1.0

    def test_negative_reward_decreases_score(self):
        c = Candidate(id="a", label="A", score=0.5)
        linkage = Linkage()
        linkage.adjust_pressure(c, outcome_reward=-1.0, learning_rate=0.1)
        assert c.score == 0.4


class TestRunCycle:
    def test_basic_cycle(self):
        candidates = [
            Candidate(id="a", label="A", score=0.9),
            Candidate(id="b", label="B", score=0.6),
            Candidate(id="c", label="C", score=0.3),
        ]
        linkage = Linkage()
        result = linkage.run_cycle(candidates, top_k=2, tag="test")
        assert len(result["selected"]) == 2
        assert result["selected"][0].id == "a"
        assert result["strategy"] == "softmax"

    def test_can_select_one(self):
        c = [Candidate(id="x", label="X", score=100)]
        result = Linkage().run_cycle(c, top_k=1, tag="single")
        assert len(result["selected"]) == 1
        assert result["selected"][0].id == "x"


class TestRecordOutcome:
    def test_adjusts_matching_candidate(self):
        c = Candidate(id="match", label="Match", score=0.5)
        linkage = Linkage()
        result = linkage.record_outcome(
            decision_id="match",
            expected=1.0,
            actual=0.9,
            candidates=[c],
            strategy="binary",
            learning_rate=0.1,
        )
        assert result["outcome"].reward == -1.0  # binary: 0.9 != 1.0
        assert result["outcome"].decision_id == "match"
        assert c.score < 0.5  # decreased due to negative reward

    def test_no_candidates_no_error(self):
        linkage = Linkage()
        result = linkage.record_outcome("orphan", expected=1, actual=1)
        assert result["outcome"] is not None
        assert result["adjusted_candidates"] == []


class TestIntegration:
    def test_full_cycle_with_feedback(self):
        candidates = [
            Candidate(id="a", label="A", score=0.8),
            Candidate(id="b", label="B", score=0.4),
        ]
        linkage = Linkage()
        cycle = linkage.run_cycle(candidates, top_k=1, tag="integ")
        selected = cycle["selected"]
        assert len(selected) == 1
        assert selected[0].id == "a"

        # Record outcome — a was correct
        fb = linkage.record_outcome(
            decision_id="a",
            expected="good",
            actual="good",
            candidates=candidates,
            strategy="binary",
        )
        # The selected candidate should have increased score
        assert candidates[0].score > 0.8
