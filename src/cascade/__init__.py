"""
cascade — AI Agent tool-call governance.

Guard LLM tool invocations with rules, scoring, and audit trails.
"""

from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass, field

from cascade._store import Store
from cascade._audit import AuditTrail
from cascade.c1_gate import ConditionVerifier
from cascade.c2_trigger import TriggerEngine
from cascade.c3_selector import Candidate, SelectionPressure
from cascade.c4_feedback import FeedbackLoop, Outcome
from cascade.linkage import Linkage

__all__ = [
    "AuditTrail",
    "Candidate",
    "ConditionVerifier",
    "DecisionPipeline",
    "FeedbackLoop",
    "Linkage",
    "Outcome",
    "SelectionPressure",
    "Store",
    "ToolCall",
    "TriggerEngine",
]


@dataclass
class ToolCall:
    """A candidate tool invocation from an LLM.

    Fields mirror the standard OpenAI / LangChain tool-call shape:
    ``id``, ``name``, ``arguments``, and an optional ``confidence``
    score (e.g. from logprobs) used by selection strategies.
    """

    id: str
    name: str
    arguments: dict = field(default_factory=dict)
    confidence: float = 0.0


class DecisionPipeline:
    """High-level orchestrator for LLM tool-call governance.

    Usage::

        pipe = DecisionPipeline()
        result = pipe.guard(
            tool_calls=[
                {"id": "s1", "name": "web_search", "confidence": 0.9},
                {"id": "d1", "name": "delete_file", "confidence": 0.3},
            ],
            rules=[{"field": "confidence", "op": "gte", "value": 0.5}],
            strategy="softmax",
            top_k=1,
        )
        if result["selected"]:
            tool = result["selected"][0]
            print(f"Selected: {tool.name} (audit: {result['audit_id']})")
    """

    def __init__(self, store: Optional[Store] = None, audit: Optional[AuditTrail] = None):
        store = store or Store()
        self._store = store
        self.audit = audit or AuditTrail()
        self.gate = ConditionVerifier()
        self.trigger = TriggerEngine()
        self.selector = SelectionPressure(store=store)
        self.feedback = FeedbackLoop(store=store)
        self.linkage = Linkage(selector=self.selector, feedback=self.feedback, store=store)

    # ── primary API ────────────────────────────────────────────────

    def guard(
        self,
        tool_calls: list[dict],
        rules: Optional[list[dict]] = None,
        strategy: str = "softmax",
        top_k: int = 1,
        context: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        """Govern tool-call selection in one call.

        1. Convert raw dicts → ``Candidate`` objects.
        2. Verify each candidate against *rules* (C₁ gate).
        3. Rank survivors via C₃ selection pressure.
        4. Write audit trail.
        5. Return structured result.

        Parameters
        ----------
        tool_calls:
            List of ``{"id": …, "name": …, "arguments": …, "confidence": …}``.
        rules:
            Rule list passed to ``ConditionVerifier``.  Each dict is
            ``{"field": …, "op": …, "value": …}`` — applied to every
            individual tool-call dict.
        strategy:
            Selection strategy — ``softmax``, ``linear``, ``uniform``,
            ``threshold``.
        top_k:
            Number of tool calls to retain after selection.
        context:
            Optional context dict also verified against *rules* (all
            tool calls must pass AND context must pass).

        Returns
        -------
        dict with keys: ``passed``, ``selected``, ``rejected``,
        ``audit_id``, ``gate_results``.
        """
        rules = rules or []
        context = context or {}

        # 1. Convert to Candidates
        candidates = [
            Candidate(
                id=tc.get("id", f"tc_{i}"),
                label=tc.get("name", "unknown"),
                score=float(tc.get("confidence", 0.0)),
                metadata={"arguments": tc.get("arguments", {}), **tc.get("metadata", {})},
            )
            for i, tc in enumerate(tool_calls)
        ]

        # 2. Gate — check context against ALL rules, then each tool call
        #    against rules whose field exists in that tool call's dict.
        context_passed = True
        context_details: list[dict] = []
        if context:
            ctx_gate = ConditionVerifier()
            for r in rules:
                ctx_gate.add_rule(r["field"], r["op"], r["value"])
            context_passed, context_details = ctx_gate.evaluate(context)

        gate_details: list[dict] = []
        surviving: list[Candidate] = []

        for tc in tool_calls:
            tc_gate = ConditionVerifier()
            for r in rules:
                if r["field"] in tc:
                    tc_gate.add_rule(r["field"], r["op"], r["value"])
            flat = {k: v for k, v in tc.items() if not isinstance(v, dict)}
            tc_passed, tc_details = tc_gate.evaluate(flat)

            passed = tc_passed and context_passed
            details = tc_details
            if not context_passed:
                details = context_details + details

            if passed:
                idx = tool_calls.index(tc)
                surviving.append(candidates[idx])

            gate_details.append(
                {
                    "tool_id": tc.get("id"),
                    "tool_name": tc.get("name"),
                    "passed": passed,
                    "details": details,
                }
            )

        all_gate_pass = context_passed and (
            not gate_details or any(g["passed"] for g in gate_details)
        )

        result: dict[str, Any] = {
            "passed": all_gate_pass,
            "selected": [],
            "rejected": [],
            "gate_results": gate_details,
        }

        # 3. Selection — discard candidates with zero pressure (e.g. threshold rejects)
        if surviving:
            ranked = self.selector.rank(surviving, strategy=strategy, **kwargs)
            ranked = [c for c in ranked if c.pressure > 0]
            selected = self.selector.select(ranked, top_k=top_k)
            result["selected"] = [
                {
                    "id": c.id,
                    "name": c.label,
                    "confidence": c.score,
                    "pressure": c.pressure,
                    "arguments": c.metadata.get("arguments", {}),
                }
                for c in selected
            ]
            rejected = [c for c in ranked if c not in selected]
            result["rejected"] = [
                {
                    "id": c.id,
                    "name": c.label,
                    "confidence": c.score,
                    "pressure": c.pressure,
                    "reason": "ranked below top_k",
                }
                for c in rejected
            ]

        # 4. Audit
        audit_entry = {
            "tool_name": result["selected"][0]["name"] if result["selected"] else None,
            "status": "selected" if result["selected"] else ("rejected" if not all_gate_pass else "no_survivors"),
            "n_candidates": len(tool_calls),
            "n_selected": len(result["selected"]),
            "n_rejected": len(result["rejected"]),
            "strategy": strategy,
            "top_k": top_k,
            "rules": rules,
        }
        result["audit_id"] = self.audit.record(audit_entry)

        return result

    # ── low-level convenience (unchanged) ──────────────────────────

    def set_gate_rules(self, rules: list[dict]) -> "DecisionPipeline":
        for r in rules:
            self.gate.add_rule(r["field"], r["op"], r["value"])
        return self

    def verify_gate(self, context: dict) -> bool:
        return self.gate.verify(context)

    def evaluate_triggers(self, context: dict) -> list[dict]:
        return self.trigger.evaluate(context)

    def select(self, candidates: list[Candidate], strategy: str = "softmax", top_k: int = 1, **kwargs) -> list[Candidate]:
        ranked = self.selector.rank(candidates, strategy=strategy, **kwargs)
        return self.selector.select(ranked, top_k=top_k)

    def record(self, decision_id: str, expected: Any, actual: Any, strategy: str = "binary", **kwargs) -> Outcome:
        return self.feedback.record(decision_id, expected, actual, strategy=strategy, **kwargs)

    def run_cycle(
        self,
        candidates: list[Candidate],
        context: dict,
        strategy: str = "softmax",
        top_k: int = 1,
        **kwargs,
    ) -> dict:
        result = self.linkage.run_cycle(candidates, top_k=top_k, strategy=strategy, **kwargs)
        result["gate_passed"] = self.verify_gate(context)
        result["triggers_fired"] = self.trigger.evaluate(context)
        return result

    def summary(self) -> dict:
        return {
            "gate": self.gate.summary(),
            "trigger": self.trigger.summary(),
            "selector": {"module": "C3 (Selector)"},
            "feedback": self.feedback.summary(),
            "linkage": {"module": "C3-C4 Linkage"},
        }
