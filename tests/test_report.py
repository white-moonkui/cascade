"""Tests for compliance report export (JSON/HTML)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cascade._audit import AuditTrail
from cascade.audit._report import export_json, export_html, _compute_stats


@pytest.fixture
def trail_path():
    """Create a temporary audit trail with sample entries."""
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "audit.jsonl"
    trail = AuditTrail(path=str(path))
    #
    trail.record({"tool_name": "search", "status": "selected", "n_candidates": 3, "n_selected": 1,
                   "strategy": "softmax", "top_k": 1, "rules": []})
    trail.record({"tool_name": "delete", "status": "rejected", "n_candidates": 2, "n_selected": 0,
                   "strategy": "threshold", "top_k": 1, "rules": [{"field": "name", "op": "nin", "value": ["delete"]}]})
    trail.record({"tool_name": "search", "status": "selected", "n_candidates": 2, "n_selected": 1,
                   "strategy": "softmax", "top_k": 1, "rules": []})
    trail.record({"tool_name": "exec", "status": "no_survivors", "n_candidates": 1, "n_selected": 0,
                   "strategy": "threshold", "top_k": 1, "rules": [{"field": "confidence", "op": "gte", "value": 0.5}]})
    return path


class TestComputeStats:
    def test_stats_counts(self, trail_path):
        entries = [json.loads(l) for l in trail_path.read_text().splitlines() if l.strip()]
        stats = _compute_stats(entries)
        assert stats["n_total"] == 4
        assert stats["n_selected"] == 2
        assert stats["n_rejected"] == 1
        assert stats["n_no_survivors"] == 1
        assert stats["block_rate"] == 50.0

    def test_stats_tools(self, trail_path):
        entries = [json.loads(l) for l in trail_path.read_text().splitlines() if l.strip()]
        stats = _compute_stats(entries)
        assert set(stats["tools"].keys()) == {"search", "delete", "exec"}
        assert stats["tools"]["search"]["total"] == 2
        assert stats["tools"]["search"]["selected"] == 2
        assert stats["tools"]["delete"]["rejected"] == 1


class TestExportJSON:
    def test_export_returns_dict(self, trail_path):
        report = export_json(trail_path)
        assert isinstance(report, dict)
        assert "metadata" in report
        assert "entries" in report
        assert report["metadata"]["n_total"] == 4
        assert len(report["entries"]) == 4

    def test_export_writes_file(self, trail_path):
        out = trail_path.parent / "report.json"
        report = export_json(trail_path, output=out)
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["metadata"]["n_total"] == 4

    def test_export_empty(self):
        tmp = tempfile.mkdtemp()
        empty = Path(tmp) / "empty.jsonl"
        empty.touch()
        report = export_json(empty)
        assert report["metadata"]["n_total"] == 0
        assert report["entries"] == []


class TestExportHTML:
    def test_export_returns_html(self, trail_path):
        html = export_html(trail_path)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "cascade" in html
        assert "SELECTED" in html
        assert "REJECTED" in html
        assert "2" in html  # n_selected

    def test_export_writes_file(self, trail_path):
        out = trail_path.parent / "report.html"
        export_html(trail_path, output=out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_export_empty(self):
        tmp = tempfile.mkdtemp()
        empty = Path(tmp) / "empty.jsonl"
        empty.touch()
        html = export_html(empty)
        assert "0" in html or "No data" in html

    def test_export_no_audit_file(self):
        tmp = tempfile.mkdtemp()
        missing = Path(tmp) / "nonexistent.jsonl"
        html = export_html(missing)
        assert "0" in html


class TestPipelineReport:
    def test_audit_report_json(self, trail_path):
        from cascade import DecisionPipeline
        pipe = DecisionPipeline(audit=AuditTrail(path=str(trail_path)))
        report = pipe.audit_report(format="json")
        assert report["metadata"]["n_total"] == 4

    def test_audit_report_html(self, trail_path):
        from cascade import DecisionPipeline
        pipe = DecisionPipeline(audit=AuditTrail(path=str(trail_path)))
        html = pipe.audit_report(format="html")
        assert "<!DOCTYPE html>" in html

    def test_audit_report_invalid_format(self, trail_path):
        from cascade import DecisionPipeline
        pipe = DecisionPipeline(audit=AuditTrail(path=str(trail_path)))
        with pytest.raises(ValueError, match="Unknown report format"):
            pipe.audit_report(format="csv")
