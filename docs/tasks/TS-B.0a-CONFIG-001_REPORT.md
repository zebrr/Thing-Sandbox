# Task TS-B.0a-CONFIG-001 Completion Report

## Summary

Extended `SimulationConfig` class with three new fields for run mode configuration:
- `default_mode` — "single" or "continuous"
- `default_interval` — seconds between ticks (default: 600)
- `default_ticks_limit` — max ticks, 0 = unlimited (default: 0)

## Changes Made

- `src/config.py`: Added three new fields to `SimulationConfig` class (lines 61-63)
- `config.toml`: Added new parameters to `[simulation]` section (lines 3-5)
- `tests/unit/test_config.py`: Added 16 new test cases for new fields:
  - 13 tests in `TestSimulationConfig` class for direct model validation
  - 3 tests in `TestConfigLoad` class for Config.load() integration

## Tests

- Result: PASS (44 tests total)
- Existing tests modified: None
- New tests added:
  - `test_default_mode_single`
  - `test_default_mode_continuous`
  - `test_default_mode_default_value`
  - `test_default_interval_valid`
  - `test_default_interval_minimum_boundary`
  - `test_default_interval_default_value`
  - `test_default_ticks_limit_zero`
  - `test_default_ticks_limit_positive`
  - `test_default_ticks_limit_default_value`
  - `test_default_mode_invalid`
  - `test_default_interval_invalid`
  - `test_default_ticks_limit_negative_invalid`
  - `test_load_default_mode_invalid`
  - `test_load_default_interval_invalid`
  - `test_load_new_simulation_fields`

## Quality Checks

- ruff check: PASS
- ruff format: PASS
- mypy: PASS

## Issues Encountered

None

## Next Steps

None — fields are ready for use by CLI in phase B.0c

## Commit Proposal

`feat: extend SimulationConfig with run parameters`

## Specs Updated

- `docs/specs/core_config.md` — status changed from IN_PROGRESS to READY
