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

Zero external dependencies.  Optional extras extend the feature set:

```bash
pip install cascade[openai]     # OpenAI SDK adapter
pip install cascade[langchain]  # LangChain adapter
pip install cascade[yaml]       # YAML policy files + cascade policy lint
```

## Adapters

Framework-specific adapters let you plug cascade governance into your
existing agent code with minimal changes.  Each adapter is a thin (<80 lines)
layer — zero impact on the core codebase.

```python
# OpenAI — auto-govern every chat.completions.create
from openai import OpenAI
from cascade import DecisionPipeline
from cascade.adapters.openai import wrap_openai_client

client = wrap_openai_client(
    OpenAI(),
    pipeline=DecisionPipeline(),
    rules=[{"field": "name", "op": "nin", "value": ["delete_file", "exec"]}],
)
```

```python
# LangChain — post-process agent output
from cascade.adapters.langchain import guard_agent_output

result = agent.invoke({"input": "search for papers on AI safety"})
result = guard_agent_output(result, pipeline=pipe, rules=[...])
```

## Why cascade?

- **Zero dependencies** — pure Python, no pip wars
- **Plugs into any LLM framework** — OpenAI, LangChain, or custom
- **Audit built in** — every `guard()` auto-writes JSONL audit trails
- **4 selection strategies** — softmax / linear / uniform / threshold
- **Self-emergence** — C₃↔C₄ closed loop learns from outcomes
- **Composite rules** — `all_of` / `any_of` / `not_` for complex policies
- **Actions** — `block` / `redirect` / `transform` for automated remediation

## Policies

Define governance rules in YAML for repeatable, audit-friendly policies.

```yaml
# policy.yaml
name: strict-tools
description: Block dangerous tools
rules:
  - field: name
    op: nin
    value: [delete_file, exec, rm]
  - field: confidence
    op: gte
    value: 0.7
  - all_of:
      - field: name
        op: eq
        value: code_interpreter
      - field: confidence
        op: gte
        value: 0.9

strategy: softmax
top_k: 1
```

```bash
cascade policy lint policy.yaml
cascade check --tool-calls @tools.json --policy policy.yaml
```

Composite rules (``all_of`` / ``any_of`` / ``not_``), ``@import`` directives, and
full schema validation are supported.

## Audit chain integrity

Every ``guard()`` decision is recorded in a SHA-256 hash-chained JSONL audit
trail.  Each entry links to its predecessor via ``prev_hash``, making the log
tamper-evident.

```bash
cascade audit verify
```

```python
from cascade._audit import AuditTrail

trail = AuditTrail()
result = trail.verify()  # {'valid': True, 'entries': 42, ...}
```

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
| [docs/cli.md](docs/cli.md) | `cascade check` / `policy lint` / `audit verify` CLI reference |
| [docs/owasp.md](docs/owasp.md) | OWASP Agentic Top 10 compliance mapping |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Integrations

| Framework | Adapter | Lines | Install |
|-----------|---------|-------|---------|
| [OpenAI SDK](src/cascade/adapters/openai.py) | `wrap_openai_client()` / `guard_openai_response()` | ~70 | `cascade[openai]` |
| [LangChain](src/cascade/adapters/langchain.py) | `guard_agent_output()` | ~55 | `cascade[langchain]` |

Each adapter is **opt-in** — the core stays zero-dependency.  All adapters
live in ``src/cascade/adapters/`` and import only what they need at runtime.

For custom framework integrations, use ``pipe.guard()`` directly:

```python
response = client.chat.completions.create(..., tools=my_tools)
result = pipe.guard(
    tool_calls=[{"id": t.id, "name": t.function.name, ...}],
    rules=[{"field": "name", "op": "nin", "value": BLOCKED_TOOLS}],
)
```
