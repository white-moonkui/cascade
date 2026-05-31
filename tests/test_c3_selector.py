"""Tests for C₃ — SelectionPressure."""

import pytest
from cascade.c3_selector import SelectionPressure, Candidate


def make_candidates(*score_pairs):
    return [Candidate(id=k, label=k, score=v) for k, v in score_pairs]


class TestRankUniform:
    def test_all_equal_pressure(self):
        c = make_candidates(("a", 10), ("b", 5), ("c", 1))
        ranked = SelectionPressure().rank(c, strategy="uniform")
        total = sum(c.pressure for c in ranked)
        assert abs(total - 1.0) < 0.001
        assert abs(ranked[0].pressure - ranked[1].pressure) < 0.001


class TestRankLinear:
    def test_pressure_proportional(self):
        c = make_candidates(("a", 10), ("b", 5), ("c", 1))
        ranked = SelectionPressure().rank(c, strategy="linear")
        assert ranked[0].id == "a"
        assert ranked[0].pressure > ranked[1].pressure

    def test_zero_scores(self):
        c = make_candidates(("a", 0), ("b", 0))
        ranked = SelectionPressure().rank(c, strategy="linear")
        assert all(r.pressure == 0.0 for r in ranked)


class TestRankSoftmax:
    def test_highest_score_wins(self):
        c = make_candidates(("a", 100), ("b", 1), ("c", 1))
        ranked = SelectionPressure().rank(c, strategy="softmax")
        assert ranked[0].id == "a"

    def test_temperature_dampens(self):
        c = make_candidates(("a", 10), ("b", 1))
        low_t = SelectionPressure().rank(c[:], strategy="softmax", temperature=0.5)
        high_t = SelectionPressure().rank(c[:], strategy="softmax", temperature=5.0)
        assert low_t[0].id == high_t[0].id


class TestRankThreshold:
    def test_only_above_threshold(self):
        c = make_candidates(("a", 0.9), ("b", 0.5), ("c", 0.3))
        ranked = SelectionPressure().rank(c, strategy="threshold", min_score=0.5)
        assert ranked[0].pressure == 1.0  # a: 0.9 >= 0.5
        assert ranked[1].pressure == 1.0  # b: 0.5 >= 0.5
        assert ranked[2].pressure == 0.0  # c: 0.3 < 0.5


class TestSelect:
    def test_select_top_k(self):
        c = make_candidates(("a", 10), ("b", 5), ("c", 1))
        sp = SelectionPressure()
        sp.rank(c, strategy="linear")
        selected = sp.select(c, top_k=2)
        assert len(selected) == 2
        assert selected[0].id == "a"
        assert selected[1].id == "b"

    def test_select_more_than_available(self):
        c = make_candidates(("a", 10), ("b", 5))
        sp = SelectionPressure()
        sp.rank(c, strategy="linear")
        selected = sp.select(c, top_k=10)
        assert len(selected) == 2


class TestEmptyCandidates:
    def test_rank_empty(self):
        assert SelectionPressure().rank([], strategy="uniform") == []

    def test_select_empty(self):
        assert SelectionPressure().select([], top_k=5) == []


class TestUnknownStrategy:
    def test_raises(self):
        with pytest.raises(ValueError, match="Unknown.*nonsense"):
            SelectionPressure().rank([Candidate("a", "a", 1)], strategy="nonsense")


class TestCheckpointing:
    def test_save_and_load(self, tmp_path):
        sp = SelectionPressure()
        c = make_candidates(("x", 9), ("y", 3))
        sp.rank(c, strategy="linear")
        sp.save_state("test", c)
        loaded = sp.load_state("test")
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0].id == "x"
        sp._store.delete("test")

    def test_load_missing(self):
        sp = SelectionPressure()
        assert sp.load_state("nonexistent") is None
