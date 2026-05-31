# CLI — `cascade check`

Test governance rules from the terminal without writing Python.

## Basic usage

```bash
cascade check \
  --tool-calls '[
    {"id":"1","name":"search","confidence":0.9},
    {"id":"2","name":"delete","confidence":0.2}
  ]' \
  --rules '[
    {"field":"confidence","op":"gte","value":0.5}
  ]'
```

Output:

```
Result:   ✅ PASS
Audit ID: e1b893ef8fdb

Gate results:
  ✅ search (id=1)
  ⛔ delete (id=2)
       rule failed: confidence gte 0.5 (actual: 0.2)

Selected:
  ✅ search (confidence=0.9, pressure=1.000)
```

## Loading from files

Use `@filename.json` to read from a file:

```bash
cascade check \
  --tool-calls @tools.json \
  --rules @rules.json \
  --context @context.json
```

## Options

| Flag | Description |
|------|-------------|
| `--tool-calls` | JSON array of tool calls (required) |
| `--rules` | JSON array of rules (optional) |
| `--context` | JSON context object (optional) |
| `--strategy` | `softmax`, `linear`, `uniform`, `threshold` (default: `softmax`) |
| `--top-k` | Number of tool calls to select (default: `1`) |

## Exit codes

- **0** — at least one tool call selected (PASS)
- **1** — all rejected (BLOCKED), or input error
