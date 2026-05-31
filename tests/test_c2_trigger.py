"""Tests for C₂ — TriggerEngine."""

from cascade.c2_trigger import TriggerEngine, TriggerStatus


def test_empty_evaluate():
    engine = TriggerEngine()
    assert engine.evaluate({"key": "val"}) == []


def test_register_and_fire():
    engine = TriggerEngine()
    engine.register("test", condition=lambda ctx: ctx.get("x") > 5)
    fired = engine.evaluate({"x": 10})
    assert len(fired) == 1
    assert fired[0]["name"] == "test"
    assert fired[0]["status"] == "fired"


def test_condition_not_met():
    engine = TriggerEngine()
    engine.register("test", condition=lambda ctx: ctx.get("x") > 5)
    fired = engine.evaluate({"x": 1})
    assert fired == []


def test_action_called():
    results = []

    def action(ctx):
        results.append(ctx["val"])

    engine = TriggerEngine()
    engine.register("act", condition=lambda ctx: True, action=action)
    engine.evaluate({"val": 42})
    assert results == [42]


def test_action_not_required():
    engine = TriggerEngine()
    engine.register("noop", condition=lambda ctx: True)
    fired = engine.evaluate({"x": 1})
    assert len(fired) == 1
    assert fired[0]["status"] == "fired"


def test_fire_count_tracking():
    engine = TriggerEngine()
    engine.register("cnt", condition=lambda ctx: ctx.get("x") > 0)
    engine.evaluate({"x": 1})
    engine.evaluate({"x": 2})
    engine.evaluate({"x": 3})
    fired = engine.evaluate({"x": 4})
    assert fired[0]["fire_count"] == 4


def test_last_fired_timestamp():
    engine = TriggerEngine()
    engine.register("ts", condition=lambda ctx: True)
    fired = engine.evaluate({"x": 1})
    assert fired[0]["last_fired"] is not None
    assert isinstance(fired[0]["last_fired"], str)


def test_exception_handling():
    engine = TriggerEngine()
    engine.register("bad", condition=lambda ctx: 1 / 0)
    fired = engine.evaluate({"x": 1})
    assert len(fired) == 1
    assert fired[0]["status"] == "failed"
    assert "error" in fired[0]


def test_reset():
    engine = TriggerEngine()
    engine.register("r", condition=lambda ctx: True)
    engine.evaluate({"x": 1})
    engine.reset("r")
    s = engine.summary()
    assert s["triggers"]["r"]["status"] == "idle"


def test_reset_all():
    engine = TriggerEngine()
    engine.register("a", condition=lambda ctx: True)
    engine.register("b", condition=lambda ctx: True)
    engine.evaluate({"x": 1})
    engine.reset_all()
    s = engine.summary()
    for t in s["triggers"].values():
        assert t["status"] == "idle"


def test_remove():
    engine = TriggerEngine()
    engine.register("del", condition=lambda ctx: True)
    engine.remove("del")
    assert engine.summary()["trigger_count"] == 0


def test_summary():
    engine = TriggerEngine()
    engine.register("s", condition=lambda ctx: True)
    engine.evaluate({"x": 1})
    s = engine.summary()
    assert s["module"] == "C2 (Trigger)"
    assert s["trigger_count"] == 1
    assert s["triggers"]["s"]["fire_count"] == 1


def test_multiple_triggers():
    engine = TriggerEngine()
    engine.register("low", condition=lambda ctx: ctx.get("v") < 5)
    engine.register("high", condition=lambda ctx: ctx.get("v") >= 5)
    fired = engine.evaluate({"v": 10})
    assert len(fired) == 1
    assert fired[0]["name"] == "high"
