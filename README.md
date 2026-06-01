# cascade

**Guard LLM tool calls with rules, scoring, and audit trails.**

[![PyPI version](https://badge.fury.io/py/cascade.svg)](https://badge.fury.io/py/cascade)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://github.com/white-moonkui/cascade)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/white-moonkui/cascade/actions/workflows/ci.yml/badge.svg)](https://github.com/white-moonkui/cascade/actions)

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

## Installation

```bash
pip install cascade
```

Zero external dependencies.

## Why cascade?

- **Zero dependencies** — pure Python, no pip wars
- **Plugs into any LLM framework** — OpenAI, LangChain, or custom
- **Audit built in** — every `guard()` auto-writes JSONL audit trails
- **4 selection strategies** — softmax / linear / uniform / threshold
- **Self-emergence** — C₃↔C₄ closed loop learns from outcomes
- **Composite rules** — `all_of` / `any_of` / `not_` for complex policies
- **Actions** — `block` / `redirect` / `transform` for automated remediation

## C1–C4 Architecture

```
C1 (Gate)      : Rule engine — 11 operators + AND/OR/NOT composition
C2 (Trigger)   : Event triggers — condition callbacks + state machine
C3 (Selector)  : Selection pressure — uniform/linear/softmax/threshold ranking
C4 (Feedback)  : Feedback loop — binary/proportional/threshold reward
Linkage        : C₃↔C₄ closed loop — rewards adjust future selection
```

## Docs

| File | What it covers |
|------|----------------|
| [docs/usage.md](docs/usage.md) | `guard()` API, `DecisionPipeline`, `AuditTrail` |
| [docs/rules.md](docs/rules.md) | Leaf rules, rule presets, composite rules (all_of/any_of/not_) |
| [docs/strategies.md](docs/strategies.md) | Selection strategies and when to use each |
| [docs/cli.md](docs/cli.md) | `cascade check` CLI reference |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Integrations

```python
# OpenAI SDK — intercept before tool_choice
response = client.chat.completions.create(..., tools=my_tools)
safe_tools = pipe.guard(
    tool_calls=[t.dict() for t in response.choices[0].message.tool_calls],
    rules=[{"field": "name", "op": "nin", "value": BLOCKED_TOOLS}],
)
```

```python
# LangChain — agent output goes through cascade
agent_result = agent.invoke({"input": query})
safe = pipe.guard(tool_calls=agent_tool_calls, rules=[...])
```
