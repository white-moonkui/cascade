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


@pytest.fixture
def fresh_sp():
    """Create a SelectionPressure with an isolated temp store to prevent
    state pollution across tests (especially UCB1 play-counts)."""
    import tempfile
    from cascade._store import Store
    d = tempfile.mkdtemp()
    return SelectionPressure(store=Store(store_dir=d))


class TestUCB1:
    """UCB1 — Upper Confidence Bound exploration/exploitation strategy."""

    def test_unseen_candidate_gets_large_bonus(self, fresh_sp):
        """First-seen candidates should be prioritised for exploration."""
        c = make_candidates(("known", 0.5), ("new", 0.5))
        fresh_sp.record_selection([c[0]])  # "known" has 1 play, "new" has 0
        ranked = fresh_sp.rank(c, strategy="ucb1")
        # "new" (n=0) should get the huge exploration bonus and rank first
        assert ranked[0].label == "new"

    def test_high_score_wins_with_same_play_count(self, fresh_sp):
        """When play-counts are equal, higher score wins."""
        c = make_candidates(("good", 0.9), ("bad", 0.1))
        fresh_sp.record_selection(c)  # both get 1 play
        ranked = fresh_sp.rank(c, strategy="ucb1")
        assert ranked[0].label == "good"

    def test_exploration_boost_fades_with_plays(self, fresh_sp):
        """After many plays, the exploration bonus should diminish."""
        c = make_candidates(("popular", 0.5), ("underdog", 0.6))
        # Give "popular" many plays
        for _ in range(100):
            fresh_sp.record_selection([c[0]])
        ranked = fresh_sp.rank(c, strategy="ucb1")
        # "underdog" has higher score and very few plays -> should rank higher
        assert ranked[0].label == "underdog"

    def test_exploration_weight_tunable(self):
        """Higher exploration_weight increases the bonus term."""
        import tempfile
        from cascade._store import Store
        low = SelectionPressure(store=Store(store_dir=tempfile.mkdtemp()))
        high = SelectionPressure(store=Store(store_dir=tempfile.mkdtemp()))

        c_low = make_candidates(("a", 0.5), ("b", 0.5))
        c_high = make_candidates(("a", 0.5), ("b", 0.5))
        for _ in range(5):
            low.record_selection([c_low[0]])
            high.record_selection([c_high[0]])
        low.record_selection([c_low[1]])
        high.record_selection([c_high[1]])

        # a=5 plays, b=1 play in both
        ranked_low = low.rank(c_low[:], strategy="ucb1", exploration_weight=0.1)
        ranked_high = high.rank(c_high[:], strategy="ucb1", exploration_weight=5.0)
        # The *absolute* pressure gap between a and b grows with exploration_weight
        gap_low = abs(ranked_low[1].pressure - ranked_low[0].pressure)
        gap_high = abs(ranked_high[1].pressure - ranked_high[0].pressure)
        assert gap_high > gap_low

    def test_ucb1_in_strategies_list(self):
        assert "ucb1" in SelectionPressure.STRATEGIES


class TestSelectionCounts:
    """Play-count tracking for UCB1."""

    def test_counts_start_empty(self, fresh_sp):
        assert fresh_sp.selection_counts() == {}

    def test_record_selection_increments(self, fresh_sp):
        c = make_candidates(("search", 0.9), ("calc", 0.5))
        fresh_sp.record_selection([c[0]])
        assert fresh_sp.selection_counts() == {"search": 1}
        fresh_sp.record_selection([c[0]])
        assert fresh_sp.selection_counts() == {"search": 2}

    def test_record_selection_multiple(self, fresh_sp):
        c = make_candidates(("a", 0.9), ("b", 0.5))
        fresh_sp.record_selection(c)  # both selected
        assert fresh_sp.selection_counts() == {"a": 1, "b": 1}

    def test_reset_counts_all(self, fresh_sp):
        c = make_candidates(("a", 0.9), ("b", 0.5))
        fresh_sp.record_selection(c)
        assert fresh_sp.reset_counts() == 2
        assert fresh_sp.selection_counts() == {}

    def test_reset_counts_single(self, fresh_sp):
        c = make_candidates(("a", 0.9), ("b", 0.5))
        fresh_sp.record_selection(c)
        assert fresh_sp.reset_counts("a") == 1
        assert "a" not in fresh_sp.selection_counts()
        assert fresh_sp.selection_counts() == {"b": 1}

    def test_counts_persist_across_instances(self, tmp_path):
        from cascade._store import Store
        store = Store(store_dir=str(tmp_path))
        sp1 = SelectionPressure(store=store)
        c = make_candidates(("x", 0.9), ("y", 0.5))
        sp1.record_selection([c[0]])

        sp2 = SelectionPressure(store=store)
        assert sp2.selection_counts() == {"x": 1}


class TestAdaptiveThreshold:
    """Dynamic threshold computation from feedback signals."""

    def test_default_values(self):
        t = SelectionPressure.adaptive_threshold()
        assert t == 0.3  # min_threshold when avg_reward=0

    def test_positive_reward_raises_threshold(self):
        t = SelectionPressure.adaptive_threshold(avg_reward=1.0)
        assert t > 0.3

    def test_negative_reward_lowers_threshold(self):
        t = SelectionPressure.adaptive_threshold(avg_reward=-1.0)
        assert t == 0.3  # clamped to min_threshold

    def test_clamped_to_max(self):
        t = SelectionPressure.adaptive_threshold(avg_reward=5.0)
        assert t <= 0.9

    def test_clamped_to_min(self):
        t = SelectionPressure.adaptive_threshold(avg_reward=-10.0)
        assert t >= 0.3

    def test_sensitivity_zero(self):
        t = SelectionPressure.adaptive_threshold(avg_reward=10.0, sensitivity=0.0)
        assert t == 0.3  # no effect

    def test_sensitivity_doubles_effect(self):
        low = SelectionPressure.adaptive_threshold(avg_reward=1.0, sensitivity=0.1)
        high = SelectionPressure.adaptive_threshold(avg_reward=1.0, sensitivity=0.5)
        assert high > low

    def test_custom_bounds(self):
        t = SelectionPressure.adaptive_threshold(avg_reward=0.5, min_threshold=0.1, max_threshold=0.5, sensitivity=0.5)
        # 0.1 + 0.5 * 0.5 = 0.35, within bounds
        assert abs(t - 0.35) < 0.001
