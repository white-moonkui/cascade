"""
C₁ — Condition Verifier / Gate.

Evaluates whether conditions are met for a decision to proceed.
Independent module — no internal cascade imports, no checkpoint store.
"""

from typing import Any, Optional


class ConditionVerifier:
    """
    Evaluates a set of condition rules against a given context.

    Each rule is a dict with a ``field``, ``op`` (operator), and
    ``value``, **or** a composite rule with ``compose``.

    Built-in leaf operators: ``eq``, ``ne``, ``gt``, ``gte``, ``lt``,
    ``lte``, ``in``, ``nin``, ``regex``, ``exists``, ``type``.

    Composite operators: ``all_of`` (AND), ``any_of`` (OR), ``not``.
    """

    BUILTIN_OPS: dict[str, str] = {
        "eq": "equals (==)",
        "ne": "not equals (!=)",
        "gt": "greater than (>)",
        "gte": "greater than or equal (>=)",
        "lt": "less than (<)",
        "lte": "less than or equal (<=)",
        "in": "value in collection",
        "nin": "value not in collection",
        "regex": "regex match",
        "exists": "field exists",
        "type": "type check",
    }

    def __init__(self, rules: Optional[list[dict]] = None):
        self.rules = rules or []

    def add_rule(self, field: str, op: str, value: Any) -> "ConditionVerifier":
        self.rules.append({"field": field, "op": op, "value": value})
        return self

    def verify(self, context: dict) -> bool:
        """Return ``True`` when *every* rule passes against *context*."""
        if not self.rules:
            return True
        return all(self._evaluate(r, context) for r in self.rules)

    def evaluate(self, context: dict) -> tuple[bool, list[dict]]:
        """
        Return ``(all_pass, [detail, ...])`` where each detail dict
        describes a single leaf rule or a composite node.
        """
        results: list[dict] = []
        for r in self.rules:
            detail = self._evaluate_detail(r, context)
            results.append(detail)
        return all(r["passed"] for r in results), results

    # ── internal ──────────────────────────────────────────────────────────

    def _evaluate_detail(self, rule: dict, context: dict) -> dict:
        """Evaluate one rule (leaf or composite) and return a detail dict."""
        if "compose" in rule:
            return self._evaluate_compose(rule, context)

        # Leaf rule
        try:
            passed = self._evaluate(rule, context)
        except Exception as exc:
            return {
                "rule": rule,
                "field": rule.get("field"),
                "op": rule.get("op"),
                "expected": rule.get("value"),
                "actual": str(exc),
                "passed": False,
                "error": str(exc),
            }
        actual = self._resolve_field(rule["field"], context)
        return {
            "rule": rule,
            "field": rule["field"],
            "op": rule["op"],
            "expected": rule["value"],
            "actual": actual,
            "passed": passed,
        }

    def _evaluate_compose(self, rule: dict, context: dict) -> dict:
        """Evaluate a composite rule and return a detail dict with children."""
        compose = rule["compose"]
        children = [self._evaluate_detail(r, context) for r in rule.get("rules", [])]

        if compose == "all_of":
            passed = all(c["passed"] for c in children)
        elif compose == "any_of":
            passed = any(c["passed"] for c in children)
        elif compose == "not":
            child = self._evaluate_detail(rule["rule"], context)
            passed = not child["passed"]
            children = [child]
        else:
            raise ValueError(f"Unknown composite operator: {compose}")

        return {
            "rule": rule,
            "compose": compose,
            "passed": passed,
            "children": children,
        }

    def _resolve_field(self, field: str, context: dict) -> Any:
        parts = field.split(".")
        val: Any = context
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                return None
        return val

    def _evaluate(self, rule: dict, context: dict) -> bool:
        field = rule["field"]
        op = rule["op"]
        expected = rule["value"]
        actual = self._resolve_field(field, context)

        if op == "eq":
            return actual == expected
        elif op == "ne":
            return actual != expected
        elif op == "gt":
            return (actual is not None) and (actual > expected)
        elif op == "gte":
            return (actual is not None) and (actual >= expected)
        elif op == "lt":
            return (actual is not None) and (actual < expected)
        elif op == "lte":
            return (actual is not None) and (actual <= expected)
        elif op == "in":
            return actual in expected if expected else False
        elif op == "nin":
            return actual not in expected if expected else True
        elif op == "regex":
            import re
            return bool(re.match(expected, str(actual)))
        elif op == "exists":
            return actual is not None
        elif op == "type":
            return isinstance(actual, expected) if isinstance(expected, type) else type(actual).__name__ == expected
        else:
            raise ValueError(f"Unknown operator: {op}")

    def summary(self) -> dict:
        return {
            "module": "C1 (Gate)",
            "rule_count": len(self.rules),
            "rules": self.rules,
        }
