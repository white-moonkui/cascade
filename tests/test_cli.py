"""Tests for cascade CLI."""

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cascade.cli", "check"] + list(args),
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
        env={"PYTHONPATH": "src"},
    )


def test_cli_selects_highest_confidence():
    r = _run(
        "--tool-calls",
        json.dumps([
            {"id": "a", "name": "search", "confidence": 0.9},
            {"id": "b", "name": "calc", "confidence": 0.3},
        ]),
        "--rules",
        json.dumps([{"field": "confidence", "op": "gte", "value": 0.5}]),
    )
    assert r.returncode == 0
    assert "✅ search" in r.stdout
    assert "⛔ calc" in r.stdout


def test_cli_all_rejected():
    r = _run(
        "--tool-calls",
        json.dumps([
            {"id": "a", "name": "bad", "confidence": 0.1},
        ]),
        "--rules",
        json.dumps([{"field": "confidence", "op": "gte", "value": 0.5}]),
    )
    assert r.returncode == 1
    assert "⛔ BLOCKED" in r.stdout or "Result:" in r.stdout


def test_cli_with_context(tmp_path):
    ctx_file = tmp_path / "ctx.json"
    ctx_file.write_text(json.dumps({"user_role": "admin"}))
    r = _run(
        "--tool-calls",
        json.dumps([{"id": "a", "name": "search", "confidence": 0.9}]),
        "--rules",
        json.dumps([{"field": "user_role", "op": "eq", "value": "admin"}]),
        "--context",
        f"@{ctx_file}",
    )
    assert r.returncode == 0


def test_cli_threshold_strategy():
    r = _run(
        "--tool-calls",
        json.dumps([
            {"id": "a", "name": "high", "confidence": 0.9},
            {"id": "b", "name": "low", "confidence": 0.2},
        ]),
        "--rules",
        json.dumps([]),
        "--strategy",
        "threshold",
        "--top-k",
        "2",
    )
    assert r.returncode == 0


def test_cli_file_not_found():
    r = _run(
        "--tool-calls",
        "@/nonexistent/file.json",
    )
    assert r.returncode == 1
    assert "file not found" in r.stderr.lower()


def test_cli_invalid_json():
    r = _run(
        "--tool-calls",
        "not valid json",
    )
    assert r.returncode == 1
