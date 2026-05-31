"""Tests for rule presets, composition, and actions."""

import pytest
from cascade import DecisionPipeline
from cascade.rules import (
    high_confidence,
    safe_tools,
    allow_only,
    require_role,
    field_matches,
    argument_matches,
    all_of,
    any_of,
    not_,
)
from cascade.actions import block, redirect, transform
from cascade.c1_gate import ConditionVerifier


# ── Rule presets ─────────────────────────────────────────────────────────────


class TestRulePresets:
    def test_high_confidence(self):
        r = high_confidence(0.7)
        assert r == {"field": "confidence", "op": "gte", "value": 0.7}

    def test_high_confidence_default(self):
        r = high_confidence()
        assert r["value"] == 0.5

    def test_safe_tools_default_bans_destructive(self):
        r = safe_tools()
        assert r["field"] == "name"
        assert r["op"] == "nin"
        assert "delete" in r["value"]
        assert "exec" in r["value"]

    def test_safe_tools_custom_block(self):
        r = safe_tools(block=["hammer"])
        assert r["value"] == ["hammer"]

    def test_allow_only(self):
        r = allow_only("search", "calc")
        assert r == {"field": "name", "op": "in", "value": ["search", "calc"]}

    def test_require_role(self):
        r = require_role("admin")
        assert r == {"field": "user_role", "op": "eq", "value": "admin"}

    def test_require_role_custom_field(self):
        r = require_role("editor", field="group")
        assert r == {"field": "group", "op": "eq", "value": "editor"}

    def test_field_matches(self):
        r = field_matches("cost", "lte", 0.1)
        assert r == {"field": "cost", "op": "lte", "value": 0.1}

    def test_argument_matches(self):
        r = argument_matches("path", "regex", r"^/safe/")
        assert r["field"] == "arguments.path"


# ── Rule composition ─────────────────────────────────────────────────────────


class TestRuleComposition:
    def test_all_of_passes_when_all_pass(self):
        cv = ConditionVerifier()
        cv.rules.append(all_of(
            field_matches("a", "eq", 1),
            field_matches("b", "eq", 2),
        ))
        passed, details = cv.evaluate({"a": 1, "b": 2})
        assert passed is True

    def test_all_of_fails_when_one_fails(self):
        cv = ConditionVerifier()
        cv.rules.append(all_of(
            field_matches("a", "eq", 1),
            field_matches("b", "eq", 99),
        ))
        passed, details = cv.evaluate({"a": 1, "b": 2})
        assert passed is False

    def test_any_of_passes_when_one_passes(self):
        cv = ConditionVerifier()
        cv.rules.append(any_of(
            field_matches("a", "eq", 1),
            field_matches("b", "eq", 99),
        ))
        passed, details = cv.evaluate({"a": 1, "b": 2})
        assert passed is True

    def test_any_of_fails_when_all_fail(self):
        cv = ConditionVerifier()
        cv.rules.append(any_of(
            field_matches("a", "eq", 99),
            field_matches("b", "eq", 99),
        ))
        passed, details = cv.evaluate({"a": 1, "b": 2})
        assert passed is False

    def test_not_negates(self):
        cv = ConditionVerifier()
        cv.rules.append(not_(field_matches("a", "eq", 1)))
        passed, _ = cv.evaluate({"a": 1})
        assert passed is False

    def test_not_of_failing_rule_passes(self):
        cv = ConditionVerifier()
        cv.rules.append(not_(field_matches("a", "eq", 99)))
        passed, _ = cv.evaluate({"a": 1})
        assert passed is True

    def test_nested_composition(self):
        """all_of + any_of + not_ together."""
        cv = ConditionVerifier()
        cv.rules.append(all_of(
            field_matches("role", "eq", "admin"),
            any_of(
                field_matches("confidence", "gte", 0.9),
                not_(field_matches("name", "eq", "delete")),
            ),
        ))
        # admin + high confidence → pass (first any_of branch)
        passed, _ = cv.evaluate({"role": "admin", "confidence": 0.95, "name": "delete"})
        assert passed is True

        # admin + low confidence + not delete → pass (second any_of branch)
        passed, _ = cv.evaluate({"role": "admin", "confidence": 0.3, "name": "search"})
        assert passed is True

        # admin + low confidence + delete → fail (both any_of branches fail)
        passed, _ = cv.evaluate({"role": "admin", "confidence": 0.3, "name": "delete"})
        assert passed is False


# ── Composition in guard() ───────────────────────────────────────────────────


class TestGuardComposition:
    def test_guard_with_all_of(self):
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "search", "confidence": 0.9},
                {"id": "2", "name": "delete", "confidence": 0.8},
            ],
            rules=[
                all_of(
                    high_confidence(0.7),
                    safe_tools(),
                ),
            ],
        )
        assert len(result["selected"]) == 1
        assert result["selected"][0]["name"] == "search"

    def test_guard_with_any_of(self):
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "search", "confidence": 0.3},
                {"id": "2", "name": "delete", "confidence": 0.95},
            ],
            rules=[
                any_of(
                    high_confidence(0.9),
                    allow_only("search"),
                ),
            ],
            top_k=2,
        )
        assert len(result["selected"]) == 2

    def test_guard_with_not_rule(self):
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "search", "confidence": 0.9},
                {"id": "2", "name": "delete", "confidence": 0.9},
            ],
            rules=[
                high_confidence(0.5),
                not_(field_matches("name", "eq", "delete")),
            ],
        )
        assert len(result["selected"]) == 1
        assert result["selected"][0]["name"] == "search"


# ── Actions ──────────────────────────────────────────────────────────────────


class TestActions:
    def test_block_action(self):
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "search", "confidence": 0.9},
                {"id": "2", "name": "delete", "confidence": 0.3},
            ],
            rules=[high_confidence(0.7)],
            actions={
                "delete": block("Low confidence"),
            },
        )
        assert len(result["selected"]) == 1
        assert result["selected"][0]["name"] == "search"

    def test_redirect_action_saves_rejected(self):
        """Redirect transforms a failing tool into a passing one."""
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "search", "confidence": 0.9},
                {"id": "2", "name": "delete", "arguments": {"path": "/tmp/x"}},
            ],
            rules=[
                safe_tools(),
            ],
            top_k=2,
            actions={
                "delete": redirect("safe_delete"),
            },
        )
        assert len(result["selected"]) == 2
        names = {t["name"] for t in result["selected"]}
        assert "safe_delete" in names

    def test_redirect_with_arg_transform(self):
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "write_file", "arguments": {"path": "/etc/passwd"}},
            ],
            rules=[
                argument_matches("path", "regex", r"^/safe/"),
            ],
            actions={
                "write_file": redirect("write_file", transform_args=lambda a: {**a, "path": "/safe/output"}),
            },
        )
        assert len(result["selected"]) == 1
        assert result["selected"][0]["arguments"]["path"] == "/safe/output"

    def test_transform_action_rewrites_tool(self):
        pipe = DecisionPipeline()

        def lower_confidence(tc: dict) -> dict:
            return {**tc, "name": "search", "arguments": {"q": str(tc.get("arguments", {}))}}

        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "unknown_tool", "arguments": {"raw": "data"}},
            ],
            rules=[allow_only("search")],
            actions={"unknown_tool": transform(lower_confidence)},
        )
        assert len(result["selected"]) == 1
        assert result["selected"][0]["name"] == "search"

    def test_transform_returns_none_discards(self):
        pipe = DecisionPipeline()

        def discard(tc):
            return None

        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "bad", "confidence": 0.3},
                {"id": "2", "name": "good", "confidence": 0.9},
            ],
            rules=[high_confidence(0.7)],
            actions={"bad": transform(discard)},
        )
        assert len(result["selected"]) == 1
        assert result["selected"][0]["name"] == "good"

    def test_action_not_applied_to_passing_tools(self):
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "search", "arguments": {"q": "hello"}},
            ],
            rules=[allow_only("search")],
            actions={"search": block("Should not fire")},
        )
        assert len(result["selected"]) == 1
        assert result["selected"][0]["name"] == "search"

    def test_action_redirect_still_fails_if_rule_not_met(self):
        """Redirect to another tool that also fails rules → stays rejected."""
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "bad", "arguments": {"x": 1}},
            ],
            rules=[allow_only("search")],
            actions={
                "bad": redirect("also_bad"),
            },
        )
        assert len(result["selected"]) == 0

    def test_mixed_presets_composition_and_actions(self):
        """Full integration: presets + any_of + redirect action."""
        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "1", "name": "search", "confidence": 0.95},
                {"id": "2", "name": "delete", "arguments": {"path": "/tmp/x"}, "confidence": 0.8},
                {"id": "3", "name": "exec", "confidence": 0.99},
            ],
            rules=[
                high_confidence(0.5),
                any_of(
                    safe_tools(),
                    require_role("admin"),
                ),
            ],
            context={"user_role": "user"},
            top_k=2,
            actions={
                "delete": redirect("trash"),
                "exec": block("No shell access"),
            },
        )
        names = {t["name"] for t in result["selected"]}
        assert "search" in names
        assert "trash" in names
        assert "exec" not in [t["name"] for t in result["selected"]]
