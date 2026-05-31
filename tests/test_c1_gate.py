"""Tests for C₁ — ConditionVerifier."""

from cascade.c1_gate import ConditionVerifier


def test_empty_rules_pass():
    cv = ConditionVerifier()
    assert cv.verify({"anything": 1}) is True


def test_eq_operator():
    cv = ConditionVerifier()
    cv.add_rule("status", "eq", "active")
    assert cv.verify({"status": "active"}) is True
    assert cv.verify({"status": "inactive"}) is False


def test_ne_operator():
    cv = ConditionVerifier()
    cv.add_rule("status", "ne", "banned")
    assert cv.verify({"status": "active"}) is True
    assert cv.verify({"status": "banned"}) is False


def test_gt_gte_lt_lte():
    cv = ConditionVerifier()
    cv.add_rule("age", "gt", 18)
    assert cv.verify({"age": 21}) is True
    assert cv.verify({"age": 18}) is False
    assert cv.verify({"age": 15}) is False


def test_gte():
    cv = ConditionVerifier()
    cv.add_rule("score", "gte", 70)
    assert cv.verify({"score": 70}) is True
    assert cv.verify({"score": 69}) is False


def test_lt():
    cv = ConditionVerifier()
    cv.add_rule("price", "lt", 100)
    assert cv.verify({"price": 50}) is True
    assert cv.verify({"price": 100}) is False


def test_lte():
    cv = ConditionVerifier()
    cv.add_rule("count", "lte", 5)
    assert cv.verify({"count": 5}) is True
    assert cv.verify({"count": 6}) is False


def test_in_operator():
    cv = ConditionVerifier()
    cv.add_rule("role", "in", ["admin", "moderator"])
    assert cv.verify({"role": "admin"}) is True
    assert cv.verify({"role": "user"}) is False


def test_nin_operator():
    cv = ConditionVerifier()
    cv.add_rule("ip", "nin", ["10.0.0.1", "192.168.0.1"])
    assert cv.verify({"ip": "1.1.1.1"}) is True
    assert cv.verify({"ip": "10.0.0.1"}) is False


def test_regex_operator():
    cv = ConditionVerifier()
    cv.add_rule("email", "regex", r"^[\w.]+@\w+\.\w+$")
    assert cv.verify({"email": "user@example.com"}) is True
    assert cv.verify({"email": "not-an-email"}) is False


def test_exists_operator():
    cv = ConditionVerifier()
    cv.add_rule("name", "exists", True)
    assert cv.verify({"name": "Alice"}) is True
    assert cv.verify({}) is False


def test_type_operator():
    cv = ConditionVerifier()
    cv.add_rule("count", "type", int)
    assert cv.verify({"count": 42}) is True
    assert cv.verify({"count": "42"}) is False


def test_nested_field_resolution():
    cv = ConditionVerifier()
    cv.add_rule("user.profile.age", "gte", 18)
    assert cv.verify({"user": {"profile": {"age": 25}}}) is True
    assert cv.verify({"user": {"profile": {"age": 16}}}) is False


def test_evaluate_returns_details():
    cv = ConditionVerifier()
    cv.add_rule("confidence", "gte", 0.5)
    all_pass, details = cv.evaluate({"confidence": 0.7})
    assert all_pass is True
    assert len(details) == 1
    d = details[0]
    assert d["field"] == "confidence"
    assert d["op"] == "gte"
    assert d["expected"] == 0.5
    assert d["actual"] == 0.7
    assert d["passed"] is True


def test_evaluate_with_failure():
    cv = ConditionVerifier()
    cv.add_rule("confidence", "gte", 0.9)
    all_pass, details = cv.evaluate({"confidence": 0.5})
    assert all_pass is False
    assert details[0]["passed"] is False


def test_multiple_rules_all_pass():
    cv = ConditionVerifier()
    cv.add_rule("age", "gte", 18)
    cv.add_rule("role", "in", ["admin", "user"])
    cv.add_rule("active", "eq", True)
    ctx = {"age": 25, "role": "admin", "active": True}
    assert cv.verify(ctx) is True


def test_multiple_rules_one_fails():
    cv = ConditionVerifier()
    cv.add_rule("age", "gte", 18)
    cv.add_rule("active", "eq", True)
    assert cv.verify({"age": 25, "active": False}) is False


def test_summary():
    cv = ConditionVerifier()
    cv.add_rule("a", "eq", 1)
    cv.add_rule("b", "gt", 2)
    s = cv.summary()
    assert s["module"] == "C1 (Gate)"
    assert s["rule_count"] == 2
