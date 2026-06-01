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

## ucb1

```python
result = pipe.guard(..., strategy="ucb1", top_k=1)
```

Upper Confidence Bound (UCB1) — a multi-armed bandit strategy that
balances **exploration** (try under-used tools) with **exploitation**
(prefer high-scoring tools).

The pressure is: ``score + exploration_weight * sqrt(2 * ln(N) / n)``

- *score* — the tool's current confidence / learned score
- *N* — total selections across all tools
- *n* — how many times this specific tool has been selected
- ``exploration_weight`` — controls exploration aggressiveness (default 1.0)

Unseen tools (n = 0) get a very large bonus to encourage initial
exploration. After enough plays, the bonus fades and scores dominate.

**Play-counts are tracked automatically.** Every ``guard()`` call
records the selected tools via ``record_selection()``.

```python
# View current play-counts
pipe.selection_counts()       # {'search': 42, 'calc': 15}

# Reset after redeployment
pipe.reset_selection_counts()
```

**When to use:** Production systems where you want to automatically
discover which tools perform best without manual tuning.

## Adaptive Threshold

The ``adaptive_threshold()`` method computes a dynamic ``min_score``
from C₄ feedback signals:

```python
# Uses average reward from feedback history
min_score = pipe.adaptive_threshold(
    min_threshold=0.3,   # floor (default 0.3)
    max_threshold=0.9,   # ceiling (default 0.9)
    sensitivity=0.3,     # how strongly reward affects threshold
)

result = pipe.guard(..., strategy="threshold", min_score=min_score)
```

When the system is performing well (high average reward), the threshold
rises — only highly-confident tools pass. When performance drops, the
bar lowers, allowing more exploration to find better tools.

## Summary

| Strategy | Pressure distribution | Best for |
|----------|----------------------|----------|
| softmax | Exponential (winner-heavy) | General purpose, clear leader |
| linear | Linear proportional | Wide score ranges |
| uniform | Equal | Random sampling, A/B tests |
| threshold | All 1.0 | Rules-only governance |
| ucb1 | Score + exploration bonus | Self-tuning production systems |
