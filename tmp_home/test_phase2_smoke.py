"""Smoke tests for Phase 2: audit chain + yaml loader."""
import json
import os
import sys
import tempfile

# --- Set home dir to avoid Path.home() failures ---
os.environ["HOME"] = "D:\\cascade\\tmp_home"


def test_audit_chain():
    """Verify hash-chained audit integrity + tamper detection."""
    from cascade._audit import AuditTrail

    tmp = tempfile.mkdtemp()
    trail = AuditTrail(path=os.path.join(tmp, "test.jsonl"))

    id1 = trail.record({"tool_name": "search"})
    id2 = trail.record({"tool_name": "delete", "status": "blocked"})
    id3 = trail.record({"tool_name": "list"})

    # Verify chain
    result = trail.verify()
    assert result["valid"], f"Chain should be valid: {result}"
    assert result["entries"] == 3, f"Expected 3 entries, got {result['entries']}"

    # Check hash pointers
    entries = trail.recent(10)
    assert entries[0]["prev_hash"] == "0" * 64  # genesis
    assert entries[1]["prev_hash"] == entries[0]["hash"]
    assert entries[2]["prev_hash"] == entries[1]["hash"]

    # recent / query
    assert len(trail.recent(2)) == 2
    assert len(trail.query(tool_name="search")) == 1

    print("  [PASS] Audit chain: record + verify + prev_hash linkage")

    # --- Tamper detection ---
    with open(trail.path, "r") as f:
        lines = f.readlines()
    modified = json.loads(lines[0])
    modified["tool_name"] = "TAMPERED"
    with open(trail.path, "w") as f:
        f.write(json.dumps(modified) + "\n")
        f.writelines(lines[1:])

    result = trail.verify()
    assert not result["valid"], "Chain must detect tampering"
    assert result["first_broken"] == 1, "First entry should be flagged"
    print("  [PASS] Audit chain: tamper detection")

    trail.clear()


def test_yaml_loader(policy_dir):
    """Verify YAML policy loading."""
    from cascade.policies.yaml_loader import load_policy, lint_policy

    policy = load_policy(os.path.join(policy_dir, "strict.yaml"))
    assert policy["name"] == "strict-tools"
    assert len(policy["rules"]) == 3
    assert policy["strategy"] == "softmax"
    assert policy["top_k"] == 1

    print("  [PASS] YAML loader: strict policy")

    policy2 = load_policy(os.path.join(policy_dir, "composite.yaml"))
    assert policy2["name"] == "composite-policy"
    assert len(policy2["rules"]) == 3
    # Check composite structure
    has_composite = any("all_of" in r for r in policy2["rules"])
    assert has_composite, "Composite rules should be loaded"

    print("  [PASS] YAML loader: composite rules")

    # Lint clean
    issues = lint_policy(os.path.join(policy_dir, "strict.yaml"))
    assert issues == [], f"Lint should be clean: {issues}"
    print("  [PASS] YAML loader: lint_policy clean")


if __name__ == "__main__":
    policy_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "policies")
    if not os.path.exists(policy_dir):
        os.makedirs(policy_dir)

        # Create test policy files
        strict = {
            "name": "strict-tools",
            "description": "Block dangerous tools",
            "rules": [
                {"field": "name", "op": "nin", "value": ["delete_file", "exec"]},
                {"field": "confidence", "op": "gte", "value": 0.7},
                {"field": "name", "op": "exists", "value": True},
            ],
            "strategy": "softmax",
            "top_k": 1,
        }
        with open(os.path.join(policy_dir, "strict.yaml"), "w") as f:
            import yaml
            yaml.dump(strict, f)

        composite = {
            "name": "composite-policy",
            "description": "Policy with composite rules",
            "rules": [
                {"field": "name", "op": "nin", "value": ["exec"]},
                {
                    "all_of": [
                        {"field": "confidence", "op": "gte", "value": 0.8},
                        {"field": "name", "op": "in", "value": ["search", "read"]},
                    ]
                },
                {
                    "any_of": [
                        {"field": "role", "op": "eq", "value": "admin"},
                        {"field": "confidence", "op": "gte", "value": 0.95},
                    ]
                },
            ],
            "strategy": "threshold",
            "top_k": 3,
        }
        with open(os.path.join(policy_dir, "composite.yaml"), "w") as f:
            yaml.dump(composite, f)

    print("Smoke tests for Phase 2:")
    test_audit_chain()
    test_yaml_loader(policy_dir)
    print("\nAll Phase 2 smoke tests: PASS")
