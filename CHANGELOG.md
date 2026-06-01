# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] — 2026-06 — Gemini & AutoGen Adapters

### Added
- **Gemini adapter** (`cascade[gemini]`): `guard_gemini_response()` +
  `wrap_genai_client()` — auto-govern Gemini function calls via the
  `google-genai>=1.0` SDK
- **AutoGen adapter** (`cascade[autogen]`): `guard_agent_reply()` +
  `wrap_agent()` — auto-govern AutoGen agent tool-call proposals

### Changed
- Core now exports `__version__` (duplicated in `pyproject.toml`)

## [0.7.0] — 2026-06 — Runtime Injection Detection & Compliance Reports

### Added
- **Runtime injection detection**: ``DecisionPipeline(enable_injection_detection=True)``
  — scans tool-call arguments for 20+ dangerous patterns (eval, exec, os.system,
  subprocess, rm -rf, path traversal, pickle, …)
- **Extensible scanner**: ``add_pattern()`` / ``remove_pattern()`` / ``extra_patterns`` /
  ``exclude`` kwargs for per-call customization
- **Compliance report export**: ``cascade audit export`` CLI subcommand
- **HTML reports**: Self-contained (inline CSS, no JS), with summary cards, bar
  charts, and last-100-entries table
- **JSON export**: ``cascade audit export --format json`` — full metadata + entries
- **Pipeline report API**: ``pipe.audit_report(format="json")`` /
  ``pipe.audit_report(format="html")``

## [0.6.0] — 2026-06 — Anthropic, CrewAI & MCP Adapters

### Added
- **Anthropic adapter** (`cascade[anthropic]`): `guard_anthropic_response()` +
  `wrap_anthropic_client()` — auto-govern Anthropic tool calls
- **CrewAI adapter** (`cascade[crewai]`): `guard_crew_output()` +
  `wrap_crew()` — auto-govern CrewAI kickoff outputs
- **MCP gateway** (zero-dep): `guarded_tool()` decorator +
  `MCPServerGuard` — cascade governance inside MCP tool servers
- ``GuardResult`` convenience class in `adapters._base`:
  ``allowed`` / ``allowed_ids`` / ``blocked`` / ``all_blocked`` / ``audit_id``

## [0.5.0] — 2026-06 — UCB1 Selection & Adaptive Thresholds

### Added
- **UCB1 strategy**: Upper Confidence Bound for exploration/exploitation balance — `strategy="ucb1"`
- **Play-count tracking**: `record_selection()` and `selection_counts()` — automatic per-tool selection tracking
- **Adaptive threshold**: `adaptive_threshold(avg_reward, ...)` — dynamic `min_score` from feedback signals
- **Pipeline integration**: `pipe.adaptive_threshold()`, `pipe.selection_counts()`, `pipe.reset_selection_counts()`
- **Configurable exploration weight**: `exploration_weight` kwarg for UCB1 (default 1.0)

### Changed
- `SelectionPressure.rank()` now passes `candidates` to strategy methods (required for UCB1)
- `SelectionPressure.__init__()` loads play-counts from Store on construction

## [0.4.0] — 2026-06 — Framework Adapters, Audit Chain & Policy Loader

### Added
- **OpenAI adapter**: `wrap_openai_client()` — auto-govern every `chat.completions.create` call
- **LangChain adapter**: `guard_agent_output()` — post-process agent output
- **OWASP Agentic Top 10 compliance mapping**: Full `docs/owasp.md`
- **SHA-256 audit chain**: Tamper-evident JSONL with `prev_hash` + `hash` + `verify()`
- **YAML policy loader**: `cascade/policies/yaml_loader.py` with schema validation
- **Composite rules in YAML**: `all_of` / `any_of` / `not_`; `@import` directives
- **CLI subcommands**: `cascade policy lint`, `cascade audit verify`
- **`cascade check --policy`**: Load rules directly from YAML policy files
- **Optional extras**: `cascade[openai]`, `cascade[langchain]`, `cascade[yaml]`

### Changed
- `AuditTrail.record()` now also sets `prev_hash` and `hash` fields
- CLI output uses cleaner `[PASS]/[BLOCK]/[OK]/[NO]` markers

## [0.3.0] — 2026-05 — Self-Emergence Mechanism

### Added
- **C₃↔C₄ Closed Loop**: `record_outcome()` feeds reward signals back into C₃ selection scores, creating a self-learning governance cycle
- `governance_report()`: View learned scores, feedback history, and system health at a glance
- `reset_scores(tool_name=None)`: Reset learned scores per-tool or entirely
- `emergence_scores` persistence: Scores survive pipeline restarts via `Store`
- Composite rule presets: `all_of`, `any_of`, `not_` for complex policy composition
- Action handlers: `block`, `redirect`, `transform` for automated remediation

### Changed
- `DecisionPipeline` now loads learned scores on every `guard()` call
- Scores are stored in `.cascade/store/emergence_scores.json`

---

## [0.2.0] — 2026-05 — Rule Presets & Composition

### Added
- Rule presets: `high_confidence`, `safe_tools`, `allow_only`, `block_only`, `require_role`
- `argument_matches` for nested field checks (`arguments.path`)
- `field_matches` generic factory for all operators
- Composite operators: `all_of`, `any_of`, `not_`
- CLI: `cascade check` with `--tool-calls`, `--rules`, `--context`, `--strategy`, `--top-k`
- JSON file loading via `@filename.json` syntax in CLI
- Audit trail: `pipe.audit.recent()` and `pipe.audit.query()`
- Multiple selection strategies: `softmax`, `linear`, `uniform`, `threshold`

---

## [0.1.0] — 2026-04 — Initial Release

### Added
- `DecisionPipeline` — high-level orchestrator for tool-call governance
- `ConditionVerifier` (C1) — rule engine with 11 operators
- `TriggerEngine` (C2) — state-machine event triggers
- `SelectionPressure` (C3) — ranking and selection strategies
- `FeedbackLoop` (C4) — outcome tracking and reward recording
- `Linkage` — C₃↔C₄ bridge for closed-loop learning
- `AuditTrail` — JSONL-based decision audit
- `Store` — checkpoint persistence
- Zero external dependencies
