# Contributing to cascade

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/white-moonkui/cascade.git
cd cascade

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/cascade/ tests/

# Type check
pyright src/cascade/
```

## Running Tests

```bash
# All tests with coverage
pytest tests/ -v --tb=short

# Single test file
pytest tests/test_c1_gate.py -v

# With PYTHONPATH (if not using pip install)
PYTHONPATH=src pytest tests/ -v
```

## Project Structure

```
src/cascade/
├── __init__.py      # DecisionPipeline + public API
├── c1_gate.py       # ConditionVerifier — rule engine
├── c2_trigger.py    # TriggerEngine — event triggers
├── c3_selector.py   # SelectionPressure — ranking strategies
├── c4_feedback.py   # FeedbackLoop — reward tracking
├── linkage.py        # C3↔C4 bridge
├── rules.py         # Rule factory functions
├── actions.py       # Action handlers (block/redirect/transform)
├── cli.py           # cascade CLI
├── _audit.py        # AuditTrail
└── _store.py        # Store — checkpoint persistence

tests/
├── test_c1_gate.py
├── test_c2_trigger.py
├── test_c3_selector.py
├── test_c4_feedback.py
├── test_emergence.py
├── test_guard.py
├── test_linkage.py
├── test_rules.py
└── test_cli.py
```

## Adding New Operators (C1)

1. Add the operator name to `ConditionVerifier.BUILTIN_OPS` in `c1_gate.py`
2. Implement the logic in `_evaluate()` method
3. Add tests in `tests/test_c1_gate.py`

## Adding New Strategies (C3)

1. Add strategy name to `SelectionPressure.STRATEGIES`
2. Implement `_strategy_<name>()` static method
3. Add tests in `tests/test_c3_selector.py`

## Adding New Feedback Strategies (C4)

1. Add strategy name to `FeedbackLoop.STRATEGIES`
2. Implement logic in `_compute_reward()`
3. Add tests in `tests/test_c4_feedback.py`

## Pull Request Guidelines

- All existing tests must pass: `pytest tests/ -q`
- New features require tests
- Run `ruff check src/cascade/ tests/` before submitting
- Update `CHANGELOG.md` for user-facing changes

## Reporting Issues

Please include:
- Python version and cascade version
- Minimal reproduction case
- Expected vs actual behavior
