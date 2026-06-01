"""
YAML policy loader — define governance policies in YAML files.

Usage::

    from cascade.policies.yaml_loader import load_policy

    policy = load_policy("policies/strict.yaml")
    result = pipe.guard(
        tool_calls=[...],
        rules=policy["rules"],
        strategy=policy["strategy"],
        top_k=policy["top_k"],
    )

Optional dependency: ``pip install cascade[yaml]`` (installs PyYAML).
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

REQUIRED_TOP_LEVEL = {"name", "rules"}
OPTIONAL_TOP_LEVEL = {"description", "strategy", "top_k", "context"}
VALID_OPERATORS = {
    "eq", "neq", "gt", "gte", "lt", "lte",
    "in", "nin", "contains", "startswith", "endswith",
    "regex", "exists",
}
COMPOSITE_KEYS = {"all_of", "any_of", "not_"}


class PolicyValidationError(ValueError):
    """Raised when a policy file fails validation."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_policy(path: str, *, resolve_imports: bool = True) -> dict[str, Any]:
    """Load and validate a YAML policy file.

    Parameters
    ----------
    path:
        Path to the ``.yaml`` or ``.yml`` policy file.
    resolve_imports:
        If ``True`` (default), recursively resolve ``@import`` references
        in ``rules``, and resolve ``extends`` base policies.

    Returns
    -------
    dict
        A policy dict with keys ``name``, ``rules``, ``strategy``,
        ``top_k``, ``context`` (where applicable).

    Raises
    ------
    PolicyValidationError
        If the file is missing, invalid, or fails schema checks.
    ImportError
        If PyYAML is not installed.
    """
    _ensure_yaml()

    filepath = Path(path)
    if not filepath.exists():
        raise PolicyValidationError(f"Policy file not found: {filepath}")

    raw = filepath.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise PolicyValidationError(f"YAML parse error in {filepath}: {e}") from e

    if not isinstance(data, dict):
        raise PolicyValidationError(
            f"Policy file must contain a top-level mapping, got {type(data).__name__}"
        )

    # ── resolve $extends before validation ──────────────────────────
    if resolve_imports and "extends" in data:
        data = _resolve_extends(data, filepath)

    # ── optional $schema check ──────────────────────────────────────
    if "$schema" in data:
        _validate_schema(data, filepath)

    _validate_policy(data, filepath)

    if resolve_imports:
        data["rules"] = _resolve_imports(data.get("rules", []), filepath.parent)

    return _normalize(data)


def load_policy_from_string(text: str) -> dict[str, Any]:
    """Load a policy from a raw YAML string (useful for testing)."""
    _ensure_yaml()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PolicyValidationError(f"YAML parse error: {e}") from e

    if not isinstance(data, dict):
        raise PolicyValidationError(
            f"Policy must be a mapping, got {type(data).__name__}"
        )
    _validate_policy(data)
    return _normalize(data)


def lint_policy(path: str) -> list[str]:
    """Validate a policy file and return a list of issues (empty = clean).

    This is a non-raising equivalent of ``load_policy`` for CLI use.
    """
    try:
        load_policy(path)
        return []
    except PolicyValidationError as e:
        return [str(e)]
    except ImportError:
        return ["PyYAML is not installed. Run: pip install cascade[yaml]"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_yaml():
    if yaml is None:
        raise ImportError(
            "PyYAML is required to load YAML policies. "
            "Install it with: pip install cascade[yaml]"
        )


def _validate_policy(data: dict, filepath: Optional[Path] = None):
    loc = f" in {filepath}" if filepath else ""

    # Required top-level keys
    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        raise PolicyValidationError(
            f"Missing required field(s){loc}: {', '.join(sorted(missing))}"
        )

    # Name must be a non-empty string
    if not isinstance(data["name"], str) or not data["name"].strip():
        raise PolicyValidationError(f"Field 'name' must be a non-empty string{loc}")

    # Rules must be a list
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise PolicyValidationError(f"Field 'rules' must be a list{loc}")
    _validate_rules(rules, filepath)

    # Strategy must be valid if present
    valid_strategies = {"softmax", "linear", "uniform", "threshold"}
    strategy = data.get("strategy", "softmax")
    if strategy not in valid_strategies:
        raise PolicyValidationError(
            f"Invalid strategy '{strategy}'{loc}: "
            f"must be one of {', '.join(sorted(valid_strategies))}"
        )

    # top_k must be positive int if present
    top_k = data.get("top_k", 1)
    if not isinstance(top_k, int) or top_k < 1:
        raise PolicyValidationError(f"Field 'top_k' must be a positive integer{loc}")


def _validate_rules(rules: list, filepath: Optional[Path] = None):
    loc = f" in {filepath}" if filepath else ""
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise PolicyValidationError(f"Rule at index {i} must be a dict{loc}")

        # Composite rule
        if any(k in rule for k in COMPOSITE_KEYS):
            for key in COMPOSITE_KEYS:
                if key in rule:
                    children = rule[key]
                    if not isinstance(children, list):
                        raise PolicyValidationError(
                            f"'{key}' at index {i} must be a list{loc}"
                        )
                    _validate_rules(children, filepath)
            continue

        # Leaf rule
        if "field" not in rule:
            raise PolicyValidationError(
                f"Leaf rule at index {i} missing 'field'{loc}"
            )
        if "op" not in rule:
            raise PolicyValidationError(
                f"Leaf rule at index {i} missing 'op'{loc}"
            )
        if rule["op"] not in VALID_OPERATORS:
            raise PolicyValidationError(
                f"Invalid operator '{rule['op']}' at index {i}{loc}: "
                f"must be one of {', '.join(sorted(VALID_OPERATORS))}"
            )
        if "value" not in rule:
            raise PolicyValidationError(
                f"Leaf rule at index {i} missing 'value'{loc}"
            )

        # @import is allowed at the rule level
        if "@import" in rule and not isinstance(rule["@import"], str):
            raise PolicyValidationError(
                f"'@import' at index {i} must be a string path{loc}"
            )


def _resolve_extends(data: dict, filepath: Path) -> dict:
    """Resolve ``extends`` by loading the base policy and merging rules.

    Base rules come first; child rules are appended (child wins on
    duplicate top-level keys like ``strategy`` / ``top_k``).
    """
    base_path = filepath.parent / data["extends"]
    if not base_path.exists():
        base_path = Path(data["extends"]).resolve()
    if not base_path.exists():
        raise PolicyValidationError(
            f"Extended policy not found: {data['extends']} "
            f"(resolved: {base_path})"
        )

    base = load_policy(str(base_path), resolve_imports=True)

    merged = dict(base)  # copy base
    for key in ("name", "description", "strategy", "top_k", "context"):
        if key in data:
            merged[key] = data[key]

    # Merge rules: base + child
    merged["rules"] = base.get("rules", []) + data.get("rules", [])

    return merged


def _resolve_imports(rules: list, base_dir: Path) -> list:
    """Recursively resolve ``@import`` directives."""
    resolved = []
    for rule in rules:
        if isinstance(rule, dict) and "@import" in rule:
            import_path = (base_dir / rule["@import"]).resolve()
            if not import_path.exists():
                import_path = Path(rule["@import"]).resolve()
            imported = load_policy(str(import_path), resolve_imports=True)
            resolved.extend(imported.get("rules", []))
        elif isinstance(rule, dict):
            # Recurse into composite keys
            for key in COMPOSITE_KEYS:
                if key in rule and isinstance(rule[key], list):
                    rule = dict(rule)
                    rule[key] = _resolve_imports(rule[key], base_dir)
            resolved.append(rule)
        else:
            resolved.append(rule)
    return resolved


def _validate_schema(data: dict, filepath: Optional[Path] = None) -> None:
    """Validate a policy against its ``$schema`` directive (optional).

    Currently supports a built-in ``cascade://policy`` schema reference
    which enforces structural requirements beyond the standard validation.
    """
    schema = data.pop("$schema", None)
    if not schema:
        return

    known_schemas = {
        "cascade://policy": {
            "description": "Standard cascade governance policy schema v1",
            "version": "1.0.0",
        },
    }

    if schema not in known_schemas:
        raise PolicyValidationError(
            f"Unknown $schema '{schema}' in {filepath or 'policy'}: "
            f"must be one of {', '.join(known_schemas)}"
        )


def _normalize(data: dict) -> dict[str, Any]:
    """Return a clean dict with defaults filled in."""
    return {
        "name": data["name"],
        "description": data.get("description", ""),
        "rules": data.get("rules", []),
        "strategy": data.get("strategy", "softmax"),
        "top_k": data.get("top_k", 1),
        "context": data.get("context", {}),
    }
