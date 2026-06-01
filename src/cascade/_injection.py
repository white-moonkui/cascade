"""
Runtime injection detection — scan tool-call arguments for dangerous patterns.

Zero-dependency.  Works by JSON-dumping the arguments dict and matching
against a built-in pattern library.  Extensible via ``add_pattern`` /
``remove_pattern``.
"""

from __future__ import annotations

import json
import re
from typing import Optional

# ── built-in pattern library ──────────────────────────────────────────
# Each entry is a (name, compiled_regex) pair.  Names are used in
# audit reasons and for pattern-level exemptions.

_BUILTIN_PATTERNS: list[tuple[str, re.Pattern]] = [
    # OS command injection
    ("os.system", re.compile(r"\bos\.system\b")),
    ("subprocess.Popen", re.compile(r"\bsubprocess\.(Popen|call|run|check_output)\b")),
    ("os.popen", re.compile(r"\bos\.popen\b")),
    ("os.exec", re.compile(r"\bos\.exec\w+\b")),
    # Python code injection
    ("eval", re.compile(r"\beval\s*\(")),
    ("exec", re.compile(r"\bexec\s*\(")),
    ("__import__", re.compile(r"\b__import__\s*\(")),
    ("compile", re.compile(r"\bcompile\s*\(")),
    ("getattr_danger", re.compile(r"\bgetattr\s*\(.*__\w+__")),
    # File system danger
    ("rm_rf", re.compile(r"\brm\s+-rf\b")),
    ("chmod_777", re.compile(r"\bchmod\s*777\b")),
    ("path_traversal", re.compile(r"\.\./|\.\.\\\\")),
    # Network / download-and-exec
    ("curl_pipe_sh", re.compile(r"\bcurl\s+.*\|\s*(ba|)sh\b")),
    ("wget_pipe_sh", re.compile(r"\bwget\s+.*\|\s*(ba|)sh\b")),
    ("base64_decode_exec", re.compile(r"\bbase64\s+.*-d\s+\||echo\s+.*\|.*base64\s+-d")),
    # Unsafe Python stdlib
    ("pickle_load", re.compile(r"\bpickle\.loads?\b")),
    ("shelve_open", re.compile(r"\bshelve\.open\b")),
    ("marshal_load", re.compile(r"\bmarshal\.loads?\b")),
    # SHELLSHOCK / env injection
    ("env_var_injection", re.compile(r"\$\(|\$\{|\B`\B")),
]

# Pre-computed for fast matching — we store the tuple list AND a
# compiled list for iteration.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = list(_BUILTIN_PATTERNS)


# ── public API ────────────────────────────────────────────────────────


def scan_arguments(
    arguments: dict,
    *,
    extra_patterns: Optional[list[tuple[str, str | re.Pattern]]] = None,
    exclude: Optional[list[str]] = None,
) -> list[dict]:
    """Scan *arguments* dict for dangerous patterns.

    Parameters
    ----------
    arguments:
        Tool-call arguments dict (nested OK).
    extra_patterns:
        Additional (name, pattern) pairs.  *pattern* can be a string
        (compiled internally) or a compiled ``re.Pattern``.
    exclude:
        Pattern names to skip (case-insensitive).

    Returns
    -------
    List of match dicts ``[{"name": …, "pattern": …, "matched": …}]``.
    Empty list = safe.
    """
    exclude_set = {e.lower() for e in (exclude or [])}

    text = json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)

    # Merge built-in + extra patterns
    patterns: list[tuple[str, re.Pattern]] = list(_INJECTION_PATTERNS)
    if extra_patterns:
        for name, pat in extra_patterns:
            if isinstance(pat, str):
                pat = re.compile(pat)
            patterns.append((name, pat))

    matches: list[dict] = []
    for name, regex in patterns:
        if name.lower() in exclude_set:
            continue
        m = regex.search(text)
        if m:
            matches.append({"name": name, "pattern": regex.pattern, "matched": m.group()})
    return matches


def add_pattern(name: str, pattern: str | re.Pattern) -> None:
    """Register a custom injection pattern.

    >>> add_pattern("my_func", r"\\bmy_dangerous_func\\b")
    """
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    _INJECTION_PATTERNS.append((name, pattern))


def remove_pattern(name: str) -> bool:
    """Remove a pattern by name (case-insensitive).

    Returns ``True`` if removed, ``False`` if not found.

    >>> remove_pattern("eval")
    True
    """
    global _INJECTION_PATTERNS
    before = len(_INJECTION_PATTERNS)
    _INJECTION_PATTERNS = [(n, p) for n, p in _INJECTION_PATTERNS if n.lower() != name.lower()]
    return len(_INJECTION_PATTERNS) < before


def list_patterns() -> list[tuple[str, str]]:
    """Return all registered patterns as ``(name, regex_string)`` pairs."""
    return [(n, p.pattern) for n, p in _INJECTION_PATTERNS]
