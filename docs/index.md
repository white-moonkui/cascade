# cascade

**Guard LLM tool calls with rules, scoring, and audit trails.**

`cascade` is a lightweight governance layer for AI agent tool calls. It sits
between your LLM and tool execution — evaluate every tool call against rules,
rank survivors by strategy, and audit every decision.

## Quick Start

```python
from cascade import DecisionPipeline

pipe = DecisionPipeline()
result = pipe.guard(
    tool_calls=[
        {"id": "1", "name": "search", "confidence": 0.92},
        {"id": "2", "name": "delete", "confidence": 0.15},
    ],
    rules=[
        {"field": "confidence", "op": "gte", "value": 0.5},
        {"field": "name", "op": "nin", "value": ["delete"]},
    ],
    strategy="softmax",
    top_k=1,
)

if result["selected"]:
    safe = result["selected"][0]
    print(f"Safe: {safe['name']} ({safe['confidence']})")
```

## Why cascade?

- **Zero dependencies** — pure Python, no pip wars
- **Plugs into any LLM framework** — OpenAI, LangChain, or custom
- **Audit built in** — every guard() auto-writes JSONL audit trails
- **4 selection strategies** — softmax / linear / uniform / threshold

## Docs

| File | What it covers |
|------|----------------|
| [usage.md](usage.md) | `guard()` API, `DecisionPipeline`, `AuditTrail` |
| [rules.md](rules.md) | Leaf rules, rule presets, composite rules (all_of/any_of/not_) |
| [strategies.md](strategies.md) | Selection strategies and when to use each |
| [cli.md](cli.md) | `cascade check` CLI reference |
