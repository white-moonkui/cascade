# Rules

Rules are the core of cascade's governance. They come in two forms.

## Leaf rules

A leaf rule is a dict with three keys:

```python
{"field": "confidence", "op": "gte", "value": 0.5}
```

- **field** — the field to check (dot-notation for nesting, e.g. `arguments.path`)
- **op** — the operator
- **value** — the expected value

### Operators

| Op | Meaning | value Type | Example |
|----|---------|-----------|--------|
| `eq` | Equal | any | `{"field": "name", "op": "eq", "value": "search"}` |
| `ne` | Not equal | any | `{"field": "name", "op": "ne", "value": "delete"}` |
| `gt` | Greater than | number | `{"field": "confidence", "op": "gt", "value": 0.8}` |
| `gte` | Greater or equal | number | `{"field": "confidence", "op": "gte", "value": 0.5}` |
| `lt` | Less than | number | `{"field": "risk", "op": "lt", "value": 3}` |
| `lte` | Less or equal | number | `{"field": "cost", "op": "lte", "value": 10}` |
| `in` | In a set | list | `{"field": "name", "op": "in", "value": ["search", "calc"]}` |
| `nin` | Not in a set | list | `{"field": "name", "op": "nin", "value": ["delete", "exec"]}` |
| `regex` | Regex match | str | `{"field": "name", "op": "regex", "value": "^search_"}` |
| `exists` | Field exists | bool | `{"field": "confidence", "op": "exists", "value": true}` |
| `type` | Type check | str | `{"field": "confidence", "op": "type", "value": "number"}` |

### Field resolution

If the field exists on the tool call → checked there. Otherwise cascade
falls back to the session `context` dict. Mix tool-level and session-level
rules freely.

## Rule presets

Factory functions from `cascade.rules`:

```python
from cascade.rules import (
    high_confidence, safe_tools, require_role,
    allow_only, block_only, field_matches, argument_matches,
    all_of, any_of, not_,
)
```

| Function | Returns | Example |
|----------|---------|---------|
| `high_confidence(min_=0.5)` | `confidence >= min_` | `high_confidence(0.7)` |
| `safe_tools(block=None)` | `name not in blocklist` | blocks `delete`, `exec`, `rm`, `drop`, `shutdown` |
| `allow_only(*names)` | `name in names` | `allow_only("search", "calc")` |
| `block_only(*names)` | `name not in names` | `block_only("exec")` |
| `require_role(role, ...)` | `field == role` | `require_role("admin")` |
| `field_matches(field, op, value)` | Generic leaf | `field_matches("cost", "lte", 0.1)` |
| `argument_matches(path, op, value)` | `arguments.path` | `argument_matches("path", "regex", "^/safe/")` |

## Composite rules

### all_of (AND)

```python
all_of(high_confidence(0.7), safe_tools())
```

### any_of (OR)

```python
any_of(require_role("admin"), allow_only("search"))
```

### not_ (NOT)

```python
not_(field_matches("name", "eq", "delete"))
```

### Nested

```python
all_of(
    high_confidence(0.5),
    any_of(safe_tools(), require_role("admin")),
)
```

Composites nest arbitrarily deep.

## Using with guard()

```python
from cascade import DecisionPipeline
from cascade.rules import all_of, high_confidence, safe_tools

pipe = DecisionPipeline()
result = pipe.guard(
    tool_calls=[...],
    rules=[
        all_of(high_confidence(0.7), safe_tools()),
    ],
)
```
