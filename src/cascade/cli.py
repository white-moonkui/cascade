"""
cascade CLI — test tool-call governance rules from the terminal.

Usage::

    cascade check --tool-calls '[
        {"id":"1","name":"search","confidence":0.9},
        {"id":"2","name":"delete","confidence":0.2}
    ]' --rules '[{"field":"confidence","op":"gte","value":0.5}]'

    cascade check --tool-calls @tools.json --rules @rules.json

    cascade policy lint policy.yaml

    cascade audit verify
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


# ------------------------------------------------------------------
# cascade check
# ------------------------------------------------------------------


def _cmd_check(args: argparse.Namespace):
    tool_calls = _load_json(args.tool_calls)
    context = _load_json(args.context) if args.context else {}

    # Load rules: --policy takes precedence over --rules
    rules = []
    if args.policy:
        try:
            from cascade.policies.yaml_loader import load_policy

            policy = load_policy(args.policy)
            rules = policy["rules"]
            # Strategy / top_k from policy file override CLI defaults
            if policy["strategy"]:
                args.strategy = policy["strategy"]
            if policy["top_k"]:
                args.top_k = policy["top_k"]
            if policy["context"]:
                context = {**context, **policy["context"]}
        except ImportError:
            print(
                "Error: PyYAML is required to load policy files.\n"
                "  pip install cascade[yaml]",
                file=sys.stderr,
            )
            sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.rules:
        rules = _load_json(args.rules)

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

    print(f"Result:   {'PASS' if result['passed'] else 'BLOCKED'}")
    print(f"Audit ID: {result['audit_id']}")
    print()

    # Gate details
    print("Gate results:")
    for g in result["gate_results"]:
        icon = "PASS" if g["passed"] else "BLOCK"
        print(f"  [{icon}] {g['tool_name']} (id={g['tool_id']})")
        for d in g["details"]:
            if not d["passed"]:
                print(f"       rule failed: {d['field']} {d['op']} {d['expected']} "
                      f"(actual: {d['actual']})")
    print()

    # Selected
    if result["selected"]:
        print("Selected:")
        for t in result["selected"]:
            print(f"  [OK] {t['name']} (confidence={t['confidence']}, "
                  f"pressure={t['pressure']:.3f})")

    if result["rejected"]:
        print("Rejected:")
        for t in result["rejected"]:
            print(f"  [NO] {t['name']} — {t['reason']}")

    sys.exit(0 if result["selected"] else 1)


# ------------------------------------------------------------------
# cascade policy lint
# ------------------------------------------------------------------


def _cmd_policy_lint(args: argparse.Namespace):
    try:
        from cascade.policies.yaml_loader import lint_policy
    except ImportError:
        print(
            "Error: PyYAML is required to load policy files.\n"
            "  pip install cascade[yaml]",
            file=sys.stderr,
        )
        sys.exit(1)

    issues = lint_policy(args.file)
    if not issues:
        print(f"Policy file '{args.file}' — valid")
        sys.exit(0)

    print(f"Policy file '{args.file}' — {len(issues)} issue(s):")
    for i, issue in enumerate(issues, start=1):
        print(f"  {i}. {issue}")
    sys.exit(1)


# ------------------------------------------------------------------
# cascade audit verify
# ------------------------------------------------------------------


def _cmd_audit_verify(args: argparse.Namespace):
    from cascade._audit import AuditTrail

    if args.path:
        trail = AuditTrail(path=args.path)
    else:
        # Fallback: default AuditTrail path (may fail if HOME is unset)
        import os as _os

        default = Path(_os.path.expanduser("~/.cascade/audit.jsonl"))
        trail = AuditTrail(path=str(default))
    result = trail.verify()

    print(f"Audit file: {trail.path}")
    print(f"Entries:    {result['entries']}")
    print(f"Integrity:  {'OK' if result['valid'] else 'BROKEN'}")

    if result["errors"]:
        print()
        print("Errors:")
        for err in result["errors"]:
            print(f"  - {err}")

    sys.exit(0 if result["valid"] else 1)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


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
    check.add_argument("--policy", help="YAML policy file (optional, overrides --rules)")
    check.add_argument("--context", help="JSON object or @file.json (optional)")
    check.add_argument(
        "--strategy",
        default="softmax",
        choices=["softmax", "linear", "uniform", "threshold"],
    )
    check.add_argument("--top-k", type=int, default=1, help="Number to select")
    check.set_defaults(func=_cmd_check)

    # cascade policy
    policy = sub.add_parser("policy", help="Manage governance policies")
    policy_sub = policy.add_subparsers(title="policy-commands", required=True)

    policy_lint = policy_sub.add_parser(
        "lint", help="Validate a YAML policy file"
    )
    policy_lint.add_argument("file", help="Path to YAML policy file")
    policy_lint.set_defaults(func=_cmd_policy_lint)

    # cascade audit
    audit = sub.add_parser("audit", help="Inspect and verify audit trails")
    audit_sub = audit.add_subparsers(title="audit-commands", required=True)

    audit_verify = audit_sub.add_parser(
        "verify", help="Verify audit chain hash integrity"
    )
    audit_verify.add_argument("--path", help="Path to audit JSONL file (optional)")
    audit_verify.set_defaults(func=_cmd_audit_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
