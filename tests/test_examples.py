"""Tests that example cookbooks run without errors."""

import subprocess
import sys
from pathlib import Path


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        cwd=EXAMPLES_DIR,
        env={"PYTHONPATH": str(EXAMPLES_DIR.parent / "src")},
    )


def test_cookbook_openai_ok():
    r = _run("cookbook_openai.py")
    assert r.returncode == 0, r.stderr
    assert "安全通过" in r.stdout
    assert "审计 ID" in r.stdout


def test_cookbook_langchain_ok():
    r = _run("cookbook_langchain.py")
    assert r.returncode == 0, r.stderr
    assert "通过: True" in r.stdout


def test_demo_full_flow_ok():
    r = _run("demo_full_flow.py")
    assert r.returncode == 0, r.stderr
    assert "Demo complete" in r.stdout
    assert "read_file" in r.stdout
    assert "shell_exec" in r.stdout
