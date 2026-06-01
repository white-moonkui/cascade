"""Tests for DecisionPipeline.guard() and AuditTrail."""

import json
from pathlib import Path
import tempfile

import pytest

from cascade import DecisionPipeline, AuditTrail
from cascade._store import Store


@pytest.fixture
def isolated_store():
    """Create an isolated temp store for each test to prevent cross-test pollution."""
    d = tempfile.mkdtemp()
    return Store(store_dir=d)


# ── guard() basic ─────────────────────────────────────────────────


def test_guard_selects_highest_confidence(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    result = pipe.guard(
        tool_calls=[
            {"id": "a", "name": "search", "confidence": 0.9},
            {"id": "b", "name": "calc", "confidence": 0.5},
            {"id": "c", "name": "send_email", "confidence": 0.3},
        ],
        strategy="linear",
        top_k=1,
    )
    assert result["passed"] is True
    assert len(result["selected"]) == 1
    assert result["selected"][0]["name"] == "search"


def test_guard_top_k(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    result = pipe.guard(
        tool_calls=[
            {"id": "a", "name": "search", "confidence": 0.9},
            {"id": "b", "name": "calc", "confidence": 0.6},
            {"id": "c", "name": "email", "confidence": 0.3},
        ],
        strategy="linear",
        top_k=2,
    )
    assert len(result["selected"]) == 2
    assert result["selected"][0]["name"] == "search"
    assert result["selected"][1]["name"] == "calc"


def test_guard_rejects_by_rule(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    result = pipe.guard(
        tool_calls=[
            {"id": "a", "name": "delete_file", "confidence": 0.9},
            {"id": "b", "name": "search", "confidence": 0.7},
        ],
        rules=[{"field": "name", "op": "nin", "value": ["delete_file"]}],
        strategy="linear",
        top_k=1,
    )
    # delete_file should be rejected, search should be selected
    assert len(result["selected"]) == 1
    assert result["selected"][0]["name"] == "search"
    # check gate details
    gate_a = result["gate_results"][0]
    assert gate_a["tool_name"] == "delete_file"
    assert gate_a["passed"] is False


def test_guard_confidence_threshold(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    result = pipe.guard(
        tool_calls=[
            {"id": "a", "name": "risky_op", "confidence": 0.2},
            {"id": "b", "name": "safe_op", "confidence": 0.8},
        ],
        rules=[{"field": "confidence", "op": "gte", "value": 0.5}],
        strategy="linear",
        top_k=1,
    )
    assert len(result["selected"]) == 1
    assert result["selected"][0]["name"] == "safe_op"


def test_guard_all_rejected(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    result = pipe.guard(
        tool_calls=[
            {"id": "a", "name": "bad", "confidence": 0.1},
            {"id": "b", "name": "worse", "confidence": 0.0},
        ],
        rules=[{"field": "confidence", "op": "gte", "value": 0.5}],
    )
    assert result["passed"] is False
    assert result["selected"] == []


def test_guard_empty_tool_calls(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    result = pipe.guard(tool_calls=[])
    assert result["passed"] is True
    assert result["selected"] == []


def test_guard_no_rules_all_pass(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    result = pipe.guard(
        tool_calls=[
            {"id": "a", "name": "foo", "confidence": 0.5},
            {"id": "b", "name": "bar", "confidence": 0.3},
        ],
        top_k=2,
    )
    assert result["passed"] is True
    assert len(result["selected"]) == 2


# ── guard() with context ──────────────────────────────────────────


def test_guard_context_gate(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    # context with user_role=admin should pass
    result = pipe.guard(
        tool_calls=[{"id": "a", "name": "search", "confidence": 0.8}],
        rules=[{"field": "user_role", "op": "eq", "value": "admin"}],
        context={"user_role": "admin"},
    )
    assert result["passed"] is True
    assert len(result["selected"]) == 1

    # context with user_role=guest should fail
    result2 = pipe.guard(
        tool_calls=[{"id": "a", "name": "search", "confidence": 0.8}],
        rules=[{"field": "user_role", "op": "eq", "value": "admin"}],
        context={"user_role": "guest"},
    )
    assert result2["passed"] is False


# ── guard() strategy parameter ────────────────────────────────────


def test_guard_with_threshold_strategy(isolated_store):
    pipe = DecisionPipeline(store=isolated_store)
    result = pipe.guard(
        tool_calls=[
            {"id": "a", "name": "high", "confidence": 0.9},
            {"id": "b", "name": "mid", "confidence": 0.5},
            {"id": "c", "name": "low", "confidence": 0.2},
        ],
        strategy="threshold",
        top_k=3,
        min_score=0.5,
    )
    # threshold only passes tools with confidence >= 0.5
    selected_names = [s["name"] for s in result["selected"]]
    assert "high" in selected_names
    assert "mid" in selected_names
    assert "low" not in selected_names


# ── AuditTrail ────────────────────────────────────────────────────


def test_audit_trail_writes_entry(tmp_path):
    audit = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    audit_id = audit.record({"tool_name": "search", "status": "selected"})
    assert audit_id is not None
    lines = list(audit.path.open())
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tool_name"] == "search"
    assert entry["status"] == "selected"
    assert "timestamp" in entry


def test_audit_trail_recent(tmp_path):
    audit = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    for i in range(5):
        audit.record({"tool_name": f"tool_{i}", "status": "selected"})
    recent = audit.recent(limit=2)
    assert len(recent) == 2
    assert recent[-1]["tool_name"] == "tool_4"


def test_audit_trail_query_by_tool_name(tmp_path):
    audit = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    audit.record({"tool_name": "search", "status": "selected"})
    audit.record({"tool_name": "delete", "status": "rejected"})
    audit.record({"tool_name": "search", "status": "selected"})

    results = audit.query(tool_name="search")
    assert len(results) == 2
    assert all(r["tool_name"] == "search" for r in results)


def test_audit_trail_query_by_status(tmp_path):
    audit = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    audit.record({"tool_name": "search", "status": "selected"})
    audit.record({"tool_name": "delete", "status": "rejected"})

    results = audit.query(status="rejected")
    assert len(results) == 1
    assert results[0]["tool_name"] == "delete"


def test_audit_trail_clear(tmp_path):
    audit = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    audit.record({"tool_name": "test", "status": "selected"})
    assert audit.path.exists()
    audit.clear()
    assert not audit.path.exists()


def test_audit_trail_recent_empty(tmp_path):
    audit = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    assert audit.recent() == []


# ── guard() produces audit_id ─────────────────────────────────────


def test_guard_includes_audit_id(tmp_path):
    audit = AuditTrail(path=str(tmp_path / "guard_audit.jsonl"))
    pipe = DecisionPipeline(audit=audit)
    result = pipe.guard(
        tool_calls=[{"id": "a", "name": "search", "confidence": 0.9}],
    )
    assert "audit_id" in result
    assert len(result["audit_id"]) > 0
    # verify it was persisted
    entries = audit.recent()
    assert entries[0]["audit_id"] == result["audit_id"]
