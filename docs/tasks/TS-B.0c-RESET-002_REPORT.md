# Task TS-B.0c-RESET-002 Completion Report

## Summary

Implemented simulation reset functionality that allows restoring a simulation to its template state. Added `reset` CLI command and supporting infrastructure including template folder structure, `TemplateNotFoundError` exception, and `reset_simulation()` function.

## Changes Made

### New Files

- `simulations/_templates/demo-sim/` — template folder with:
  - `simulation.json` — simulation metadata (tick 0, paused)
  - `characters/henderson.json`, `characters/ogilvy.json`
  - `locations/horsell_pit.json`, `locations/woking_common.json`
  - `logs/.gitkeep` — empty placeholder for git tracking

- `tests/unit/test_cli.py` — new test file for CLI commands with tests:
  - `test_reset_command_success`
  - `test_reset_command_template_not_found`
  - `test_reset_command_storage_error`

### Modified Files

- `src/utils/storage.py`:
  - Added `import shutil`
  - Added `TemplateNotFoundError` exception class
  - Added `reset_simulation(sim_id, base_path)` function

- `src/cli.py`:
  - Added imports for `TemplateNotFoundError`, `reset_simulation`
  - Added `reset` command with error handling

- `tests/unit/test_storage.py`:
  - Added imports for new exception and function
  - Added `create_test_template()` helper
  - Added `TestResetSimulation` class with 5 tests

### Updated Specifications

- `docs/specs/util_storage.md`:
  - Added `TemplateNotFoundError` to Exceptions section
  - Added `reset_simulation()` to Functions section
  - Added exit code mapping for `TemplateNotFoundError`
  - Added test coverage entries for reset tests

- `docs/specs/core_cli.md`:
  - Added `reset` command documentation
  - Added `TemplateNotFoundError` to Exception Mapping
  - Added reset command tests to Test Coverage

- `docs/Thing' Sandbox Architecture.md`:
  - Added section 5.1 "Шаблоны и сброс симуляции"

## Tests

- Result: PASS (230 passed, 20 skipped)
- Existing tests modified: `test_storage.py` (added imports)
- New tests added:
  - `tests/unit/test_storage.py`: 5 tests for `reset_simulation()`
  - `tests/unit/test_cli.py`: 3 tests for `reset` command

## Quality Checks

- ruff check: PASS
- ruff format: PASS (reformatted 2 files)
- mypy: PASS

## Manual Verification

```bash
$ python -m src.cli status demo-sim
demo-sim: tick 0, 2 characters, 2 locations, status: paused

$ python -m src.cli reset demo-sim
[demo-sim] Reset to template.

$ python -m src.cli status demo-sim
demo-sim: tick 0, 2 characters, 2 locations, status: paused

$ python -m src.cli reset nonexistent-sim
Error: Template for 'nonexistent-sim' not found
(exit code 2)
```

## Issues Encountered

None

## Next Steps

None

## Commit Proposal

`feat: add simulation reset from template`

## Specs Updated

- `docs/specs/util_storage.md`
- `docs/specs/core_cli.md`
- `docs/Thing' Sandbox Architecture.md`
