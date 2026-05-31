"""Tests for C₄ — FeedbackLoop."""

import pytest
from cascade._store import Store
from cascade.c4_feedback import FeedbackLoop, Outcome


@pytest.fixture
def fb(tmp_path):
    """Fresh FeedbackLoop with isolated store for each test."""
    return FeedbackLoop(store=Store(store_dir=str(tmp_path / "checkpoints")))


class TestRecord:
    def test_binary_match(self, fb):
        o = fb.record("d1", expected=10, actual=10, strategy="binary")
        assert o.reward == 1.0

    def test_binary_mismatch(self, fb):
        o = fb.record("d1", expected=10, actual=5, strategy="binary")
        assert o.reward == -1.0

    def test_proportional(self, fb):
        o = fb.record("d1", expected=10, actual=15, strategy="proportional")
        assert o.reward == 5.0

    def test_proportional_negative(self, fb):
        o = fb.record("d1", expected=10, actual=3, strategy="proportional")
        assert o.reward == -7.0

    def test_threshold_within(self, fb):
        o = fb.record("d1", expected=10, actual=10.05, strategy="threshold", tolerance=0.1)
        assert o.reward == 1.0

    def test_threshold_outside(self, fb):
        o = fb.record("d1", expected=10, actual=11, strategy="threshold", tolerance=0.5)
        assert o.reward == -1.0

    def test_unknown_strategy(self, fb):
        with pytest.raises(ValueError, match="Unknown.*bad"):
            fb.record("d1", expected=1, actual=1, strategy="bad")


class TestHistory:
    def test_recent_returns_last_n(self, fb):
        for i in range(10):
            fb.record(f"d{i}", expected=1, actual=1, strategy="binary")
        recent = fb.recent(3)
        assert len(recent) == 3
        assert recent[0].decision_id == "d7"
        assert recent[-1].decision_id == "d9"

    def test_recent_defaults_to_10(self, fb):
        for i in range(5):
            fb.record(f"d{i}", expected=1, actual=1, strategy="binary")
        assert len(fb.recent()) == 5

    def test_average_reward(self, fb):
        fb.record("a", expected=1, actual=1, strategy="binary")
        fb.record("b", expected=1, actual=0, strategy="binary")
        fb.record("c", expected=1, actual=1, strategy="binary")
        avg = fb.average_reward()
        assert abs(avg - (1.0 / 3)) < 0.001

    def test_average_reward_empty(self, fb):
        assert fb.average_reward() == 0.0


class TestOutcomeData:
    def test_outcome_fields(self):
        o = Outcome(decision_id="d1", expected="x", actual="y", reward=0.5)
        assert o.decision_id == "d1"
        assert o.expected == "x"
        assert o.actual == "y"
        assert o.reward == 0.5
        assert o.timestamp is not None

    def test_outcome_default_reward(self):
        o = Outcome(decision_id="d1", expected=1, actual=1)
        assert o.reward == 0.0


class TestSummary:
    def test_summary_structure(self, fb):
        fb.record("d1", expected=10, actual=10, strategy="binary")
        s = fb.summary()
        assert s["module"] == "C4 (Feedback)"
        assert s["total_outcomes"] == 1
        assert "avg_reward" in s
        assert "recent" in s
