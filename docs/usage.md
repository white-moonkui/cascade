# Usage

## DecisionPipeline

```python
from cascade import DecisionPipeline

pipe = DecisionPipeline(checkpoint_path: str | None = None)
```

- `checkpoint_path` — optional path to a JSON file for persisting selector
  scores across sessions (e.g. for feedback loops).

### pipe.guard()

```python
result = pipe.guard(
    tool_calls: list[dict],
    rules: list[dict] | None = None,
    strategy: str = "softmax",
    top_k: int = 1,
    context: dict | None = None,
) -> dict
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool_calls` | `list[dict]` | (required) | List of tool call objects from your LLM |
| `rules` | `list[dict]` | `[]` | Rule list (see [rules.md](rules.md)) |
| `strategy` | `str` | `"softmax"` | Selection strategy (see [strategies.md](strategies.md)) |
| `top_k` | `int` | `1` | How many tool calls to select |
| `context` | `dict` | `{}` | Contextual data for rules that check session state |
| `actions` | `dict[str, dict]` | `None` | Action handlers keyed by tool name (see below) |

**Returns**

```python
{
    "passed": bool,           # True if at least one tool call selected
    "selected": list[dict],   # Survivors (enriched with pressure score)
    "rejected": list[dict],   # Rejected with reason
    "gate_results": list,     # Per-tool-call gate verdicts
    "audit_id": str,          # Traceable audit ID
}
```

Each selected item includes: `id`, `name`, `arguments`, `confidence`,
`pressure` (0–1 score from the selection strategy).

Each rejected item includes: `id`, `name`, `reason`.

### pipe.audit

```python
# Most recent entries (default 10)
entries = pipe.audit.recent(limit=5)

# Query by tool name
entries = pipe.audit.query(tool_name="search")

# Query by status
entries = pipe.audit.query(status="rejected")

# Clear logs
pipe.audit.clear()
```

Each audit entry contains:
`timestamp`, `audit_id`, `tool_id`, `tool_name`, `status`,
`strategy`, `top_k`, `rules`, `context`, `gate_details`.

By default the audit trail is stored in memory. Pass a directory path
to persist to JSONL files:

```python
from cascade import AuditTrail

trail = AuditTrail(dir_path="./audit_logs")
```

## ToolCall Dataclass

```python
from cascade import ToolCall

tc = ToolCall(id="1", name="search", confidence=0.9, arguments={"q": "hello"})
print(tc.name)  # "search"
```

`ToolCall` is a typed wrapper. You can pass dicts or `ToolCall` instances
to `guard()` — both work.

## Actions

Actions respond when a tool call fails governance. Use them to redirect
to a safer tool, transform the call, or block with a reason.

```python
from cascade.actions import block, redirect, transform

result = pipe.guard(
    tool_calls=[...],
    rules=[safe_tools()],
    actions={
        "delete_file": redirect("trash"),
        "shell_exec": block("Shell not allowed"),
        "unknown_tool": transform(lambda tc: {**tc, "name": "fallback"}),
    },
)
```

Actions are keyed by tool name (the `name` field on the tool-call dict).

| Action | Behavior |
|--------|----------|
| `block(reason)` | Keep the tool call rejected with a reason |
| `redirect(to_tool, transform_args=None)` | Change tool name and re-run rules |
| `transform(fn)` | Call `fn(tc)` to rewrite the tool call, then re-run rules. Return `None` to discard. |

