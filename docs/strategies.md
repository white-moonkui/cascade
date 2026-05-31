# Selection Strategies

After the gate filters out rule-violating tool calls, the selector
ranks survivors and picks the top `k`.

## softmax (default)

```python
result = pipe.guard(..., strategy="softmax", top_k=1)
```

Applies softmax normalization to confidence scores. The highest-confidence
tool call gets the lion's share of probability mass.

**When to use:** General-purpose. Best when you want a clear winner
but keep the selection probabilistic (e.g. for exploration).

## linear

```python
result = pipe.guard(..., strategy="linear", top_k=2)
```

Min-max normalizes scores to [0, 1]. Every surviving tool gets a proportional
shot based on how far it is from the min and max.

**When to use:** When scores are distributed across a wide range and you
want fair representation.

## uniform

```python
result = pipe.guard(..., strategy="uniform", top_k=1)
```

Every survivor gets equal pressure. Selection is effectively random.

**When to use:** Random sampling, A/B testing, or when you want to
avoid confidence-based bias entirely.

## threshold

```python
result = pipe.guard(..., strategy="threshold", top_k=5)
```

All survivors get pressure = 1.0. No ranking — every tool that passes the
gate is eligible. `top_k` acts as a simple limit.

**When to use:** When the rules are the only filter you need and you
don't want confidence-based ranking.

## Summary

| Strategy | Pressure distribution | Best for |
|----------|----------------------|----------|
| softmax | Exponential (winner-heavy) | General purpose, clear leader |
| linear | Linear proportional | Wide score ranges |
| uniform | Equal | Random sampling, A/B tests |
| threshold | All 1.0 | Rules-only governance |
