"""
End-to-end demo: LLM → cascade governance → execution.

Simulates a coding agent that generates tool calls.
cascade filters out dangerous or low-confidence ones.

Run: PYTHONPATH=src python3 examples/demo_full_flow.py
"""

import json
import textwrap
from cascade import DecisionPipeline


def simulate_llm_tool_calls() -> list[dict]:
    """Simulate an LLM agent deciding what to do next."""

    return [
        {
            "id": "tc_1",
            "name": "read_file",
            "arguments": {"path": "src/main.py"},
            "confidence": 0.95,
        },
        {
            "id": "tc_2",
            "name": "write_file",
            "arguments": {"path": "src/main.py", "content": "..."},
            "confidence": 0.88,
        },
        {
            "id": "tc_3",
            "name": "shell_exec",
            "arguments": {"command": "npm install"},
            "confidence": 0.72,
        },
        {
            "id": "tc_4",
            "name": "delete_file",
            "arguments": {"path": "/etc/config"},
            "confidence": 0.45,
        },
        {
            "id": "tc_5",
            "name": "git_push",
            "arguments": {"message": "wip"},
            "confidence": 0.60,
        },
        {
            "id": "tc_6",
            "name": "search_web",
            "arguments": {"query": "python 3.14 changelog"},
            "confidence": 0.81,
        },
    ]


def simulate_execution(selected: list[dict]) -> None:
    """Pretend to execute selected tool calls."""
    print("\n" + "=" * 50)
    print("  EXECUTING SELECTED TOOLS")
    print("=" * 50)
    for tool in selected:
        print(f"\n  ✅ executing: {tool['name']}")
        for k, v in tool["arguments"].items():
            preview = v if len(str(v)) < 50 else str(v)[:47] + "..."
            print(f"     {k}: {preview}")


def main():
    print(textwrap.dedent("""\
        ╔══════════════════════════════════════════╗
        ║      cascade — Tool-Call Governance      ║
        ║    End-to-End Demo Flow                  ║
        ╚══════════════════════════════════════════╝
    """))

    # Step 1: LLM generates tool calls
    print("─" * 50)
    print("  LLM  proposes 6 tool calls")
    print("─" * 50)
    tool_calls = simulate_llm_tool_calls()
    for tc in tool_calls:
        print(f"  {tc['id']:6s}  {tc['name']:15s}  "
              f"confidence={tc['confidence']}  args={tc['arguments']}")

    # Step 2: cascade governance
    print("\n" + "─" * 50)
    print("  cascade  governance")
    print("─" * 50)

    pipe = DecisionPipeline()
    result = pipe.guard(
        tool_calls=tool_calls,
        rules=[
            # Safety: block destructive operations
            {"field": "name", "op": "nin", "value": ["delete_file", "shell_exec"]},
            # Quality: only confident calls
            {"field": "confidence", "op": "gte", "value": 0.6},
            # Session-level: user role must be developer
            {"field": "user_role", "op": "eq", "value": "developer"},
        ],
        strategy="softmax",
        top_k=2,
        context={"user_role": "developer"},
    )

    # Step 3: show gate results
    print("\n  Gate results:")
    for g in result["gate_results"]:
        if g["passed"]:
            print(f"    ✅ {g['tool_name']:15s}  all rules passed")
        else:
            reasons = [
                f"{d['field']} {d['op']} {d['expected']} (got {d['actual']})"
                for d in g["details"]
                if not d["passed"]
            ]
            print(f"    ⛔ {g['tool_name']:15s}  {'; '.join(reasons)}")

    print(f"\n  Selection ({result['strategy']}, top_k={result['top_k']}):")
    print(f"    Passed:  {result['passed']}")
    print(f"    Audit:   {result['audit_id']}")

    if result["selected"]:
        print(f"\n  Selected ({len(result['selected'])}):")
        for t in result["selected"]:
            print(f"    ✅ {t['name']:15s}  "
                  f"confidence={t['confidence']}, pressure={t['pressure']:.3f}")

    if result["rejected"]:
        print(f"\n  Rejected ({len(result['rejected'])}):")
        for t in result["rejected"]:
            print(f"    ⛔ {t['name']:15s}  {t['reason']}")

    # Step 4: execute (if any)
    if result["selected"]:
        simulate_execution(result["selected"])

    # Step 5: audit trail
    print("\n" + "─" * 50)
    print("  Audit trail  (last 5 entries)")
    print("─" * 50)
    for entry in pipe.audit.recent(limit=5):
        name = (entry.get("tool_name") or "")[:15]
        print(f"  [{entry['timestamp'][:19]}] "
              f"{name:15s}  "
              f"status={entry['status']}")

    print("\n" + "=" * 50)
    print("  Done. Demo complete.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
