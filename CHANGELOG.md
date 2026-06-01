# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
