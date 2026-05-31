"""
cascade CLI — test tool-call governance rules from the terminal.

Usage::

    cascade check --tool-calls '[
        {"id":"1","name":"search","confidence":0.9},
        {"id":"2","name":"delete","confidence":0.2}
    ]' --rules '[{"field":"confidence","op":"gte","value":0.5}]'

    cascade check --tool-calls @tools.json --rules @rules.json
"""

import argparse
import json
import sys
from pathlib import Path

from cascade import DecisionPipeline


def _load_json(value: str) -> list | dict:
    """Load JSON from a string or from a file if prefixed with ``@``."""
    if value.startswith("@"):
        path = Path(value[1:])
        if not path.exists():
            print(f"Error: file not found — {path}", file=sys.stderr)
            sys.exit(1)
        return json.loads(path.read_text())
    return json.loads(value)


def _cmd_check(args: argparse.Namespace):
    tool_calls = _load_json(args.tool_calls)
    rules = _load_json(args.rules) if args.rules else []
    context = _load_json(args.context) if args.context else {}

    if not isinstance(tool_calls, list):
        print("Error: --tool-calls must be a JSON array", file=sys.stderr)
        sys.exit(1)

    pipe = DecisionPipeline()
    result = pipe.guard(
        tool_calls=tool_calls,
        rules=rules,
        strategy=args.strategy,
        top_k=args.top_k,
        context=context,
    )

    print(f"Result:   {'✅ PASS' if result['passed'] else '⛔ BLOCKED'}")
    print(f"Audit ID: {result['audit_id']}")
    print()

    # Gate details
    print("Gate results:")
    for g in result["gate_results"]:
        icon = "✅" if g["passed"] else "⛔"
        print(f"  {icon} {g['tool_name']} (id={g['tool_id']})")
        for d in g["details"]:
            if not d["passed"]:
                print(f"       rule failed: {d['field']} {d['op']} {d['expected']} "
                      f"(actual: {d['actual']})")
    print()

    # Selected
    if result["selected"]:
        print("Selected:")
        for t in result["selected"]:
            print(f"  ✅ {t['name']} (confidence={t['confidence']}, "
                  f"pressure={t['pressure']:.3f})")

    if result["rejected"]:
        print("Rejected:")
        for t in result["rejected"]:
            print(f"  ⛔ {t['name']} — {t['reason']}")

    sys.exit(0 if result["selected"] else 1)


def main():
    parser = argparse.ArgumentParser(
        prog="cascade",
        description="Guard LLM tool calls with rules, scoring, and audit trails.",
    )
    sub = parser.add_subparsers(title="commands", required=True)

    # cascade check
    check = sub.add_parser("check", help="Evaluate tool-call governance rules")
    check.add_argument("--tool-calls", required=True, help="JSON array or @file.json")
    check.add_argument("--rules", help="JSON array or @file.json (optional)")
    check.add_argument("--context", help="JSON object or @file.json (optional)")
    check.add_argument("--strategy", default="softmax",
                       choices=["softmax", "linear", "uniform", "threshold"])
    check.add_argument("--top-k", type=int, default=1, help="Number to select")
    check.set_defaults(func=_cmd_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
