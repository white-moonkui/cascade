"""Tests for the emergence mechanism — C₃ ↔ C₄ closed loop."""

from pathlib import Path
import json
import tempfile

import pytest
from cascade import DecisionPipeline
from cascade._store import Store


@pytest.fixture
def tmp_store():
    """Create a pipeline with an isolated temp store for each test."""
    d = tempfile.mkdtemp()
    store = Store(store_dir=d)
    return store, d


def test_record_outcome_persists_score(tmp_store):
    """A single positive outcome adjusts the score for next guard()."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    # Tool "search" initially has confidence 0.5 — no learned score yet
    result_1 = pipe.guard(
        tool_calls=[{"id": "1", "name": "search", "confidence": 0.5}],
        rules=[],
    )
    assert result_1["selected"][0]["confidence"] == 0.5

    # Feed positive feedback
    outcome = pipe.record_outcome("search", reward=1.0, learning_rate=0.2)
    assert outcome["old_score"] == 0.0
    assert outcome["new_score"] == 0.2
    assert outcome["tool_name"] == "search"

    # Next guard() uses learned score (0.2) instead of confidence (0.5)
    result_2 = pipe.guard(
        tool_calls=[{"id": "2", "name": "search", "confidence": 0.5}],
        rules=[],
    )
    assert result_2["selected"][0]["confidence"] == 0.2


def test_negative_feedback_lowers_score(tmp_store):
    """Negative reward decreases the learned score."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    pipe.record_outcome("delete", reward=-1.0, learning_rate=0.3)
    # score should be -0.3

    result = pipe.guard(
        tool_calls=[{"id": "1", "name": "delete", "confidence": 0.9}],
        rules=[],
    )
    # learned = -0.3, which exists and is used despite being negative
    assert result["selected"][0]["confidence"] == -0.3


def test_multiple_feedback_accumulates(tmp_store):
    """Repeated positive feedback compounds."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    for _ in range(5):
        pipe.record_outcome("search", reward=1.0, learning_rate=0.1)

    # score = 5 * 0.1 = 0.5
    result = pipe.guard(
        tool_calls=[{"id": "1", "name": "search", "confidence": 0.3}],
        rules=[],
    )
    assert result["selected"][0]["confidence"] == 0.5


def test_emergence_changes_selection(tmp_store):
    """Positive feedback makes a tool more likely to be selected over another."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    # Two tools: A (conf=0.7) and B (conf=0.6)
    # Initially A wins (higher confidence)
    r1 = pipe.guard(
        tool_calls=[
            {"id": "1", "name": "tool_a", "confidence": 0.7},
            {"id": "2", "name": "tool_b", "confidence": 0.6},
        ],
        rules=[],
        top_k=1,
    )
    assert r1["selected"][0]["name"] == "tool_a"

    # Feed B lots of positive feedback
    for _ in range(10):
        pipe.record_outcome("tool_b", reward=1.0, learning_rate=0.1)

    # Now B's learned score = 1.0, while A has no learned score (uses 0.7)
    r2 = pipe.guard(
        tool_calls=[
            {"id": "1", "name": "tool_a", "confidence": 0.7},
            {"id": "2", "name": "tool_b", "confidence": 0.6},
        ],
        rules=[],
        top_k=1,
    )
    assert r2["selected"][0]["name"] == "tool_b"


def test_governance_report_shape(tmp_store):
    """governance_report() returns expected keys."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    report = pipe.governance_report()
    assert "scores" in report
    assert "n_tools_tracked" in report
    assert "total_feedback" in report
    assert "average_reward" in report

    # After feedback, report shows data
    pipe.record_outcome("search", reward=1.0)
    report = pipe.governance_report()
    assert report["n_tools_tracked"] == 1
    assert "search" in report["scores"]


def test_reset_scores_clears_all(tmp_store):
    """reset_scores() wipes learned scores."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    pipe.record_outcome("search", reward=1.0, learning_rate=0.3)
    assert pipe.governance_report()["n_tools_tracked"] == 1

    n = pipe.reset_scores()
    assert n == 1
    assert pipe.governance_report()["n_tools_tracked"] == 0


def test_reset_scores_single_tool(tmp_store):
    """reset_scores(tool_name) only clears that tool."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    pipe.record_outcome("search", reward=1.0)
    pipe.record_outcome("delete", reward=-1.0)

    assert pipe.governance_report()["n_tools_tracked"] == 2

    pipe.reset_scores("search")
    report = pipe.governance_report()
    assert report["n_tools_tracked"] == 1
    assert "delete" in report["scores"]


def test_scores_survive_new_pipeline_instance(tmp_store):
    """Scores persist in Store across different DecisionPipeline instances."""
    store, _ = tmp_store
    pipe_a = DecisionPipeline(store=store)
    pipe_a.record_outcome("search", reward=1.0, learning_rate=0.5)
    # score = 0.5

    pipe_b = DecisionPipeline(store=store)
    result = pipe_b.guard(
        tool_calls=[{"id": "1", "name": "search", "confidence": 0.2}],
        rules=[],
    )
    assert result["selected"][0]["confidence"] == 0.5


def test_feedback_appears_in_recent_feedback(tmp_store):
    """record_outcome entries show up in governance_report recent_feedback."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    pipe.record_outcome("search", reward=1.0)
    report = pipe.governance_report()
    assert len(report["recent_feedback"]) >= 1
    last = report["recent_feedback"][-1]
    assert last["decision_id"] == "search"


def test_unseen_tool_uses_confidence(tmp_store):
    """A tool that has never received feedback uses its raw confidence."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    result = pipe.guard(
        tool_calls=[{"id": "1", "name": "brand_new_tool", "confidence": 0.77}],
        rules=[],
    )
    assert result["selected"][0]["confidence"] == 0.77


def test_emergence_with_rules_and_selection(tmp_store):
    """Full cycle: gate + feedback + changing selection outcome."""
    store, _ = tmp_store
    pipe = DecisionPipeline(store=store)

    # Start equal
    for _ in range(3):
        pipe.record_outcome("reliable_tool", reward=0.5, learning_rate=0.2)
    # reliable_tool score = 0.3

    # guard() with rules
    result = pipe.guard(
        tool_calls=[
            {"id": "1", "name": "reliable_tool", "confidence": 0.1},
            {"id": "2", "name": "risky_tool", "confidence": 0.9},
        ],
        rules=[{"field": "name", "op": "nin", "value": ["risky_tool"]}],
        top_k=1,
    )
    # risky_tool blocked by rules → reliable_tool selected (learned score 0.3)
    assert len(result["selected"]) == 1
    assert result["selected"][0]["name"] == "reliable_tool"
