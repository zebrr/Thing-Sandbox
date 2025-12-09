# Task TS-BACKLOG-005-CONFIG-001 Completion Report

## Summary

Successfully prepared Config infrastructure for TelegramNarrator by expanding TelegramOutputConfig, removing unused console.enabled field, adding Config.resolve_output() method for merging config.toml defaults with simulation.json overrides, and restructuring CLI flow to load simulation before creating narrators.

## Changes Made

### Source Files

- **src/config.py**:
  - Removed `enabled` field from `ConsoleOutputConfig` (keep only `show_narratives`)
  - Added new fields to `TelegramOutputConfig`: `mode`, `group_intentions`, `group_narratives`
  - Added `Config.resolve_output(simulation)` method for merging config.toml defaults with simulation.json overrides
  - Used `TYPE_CHECKING` to avoid circular import with Simulation

- **src/runner.py**:
  - Changed `run_tick(sim_id: str)` signature to `run_tick(simulation: Simulation, sim_path: Path)`
  - Removed `load_simulation` import (simulation loading moved to CLI)
  - Added `Path` import

- **src/cli.py**:
  - Updated run command flow: load simulation BEFORE creating narrators
  - Added `config.resolve_output(simulation)` call to get merged output config
  - Pass `show_narratives` from resolved config to ConsoleNarrator
  - Updated `_run_tick` signature to accept simulation, sim_path, output_config

### Configuration Files

- **config.toml**:
  - Removed `enabled` from `[output.console]`
  - Added new fields to `[output.telegram]`: `mode`, `group_intentions`, `group_narratives`

- **simulations/demo-sim/simulation.json**: Added `output` section with telegram overrides
- **simulations/_templates/demo-sim/simulation.json**: Added `output` section with telegram overrides

### Test Files

- **tests/unit/test_config.py**:
  - Removed tests for `console.enabled`
  - Added tests for new telegram fields (mode, group_intentions, group_narratives)
  - Added `TestResolveOutput` class with 5 tests for resolve_output method

- **tests/unit/test_runner.py**:
  - Removed `test_run_tick_simulation_not_found` (responsibility moved to CLI)
  - Updated all `run_tick()` calls to use new signature `run_tick(simulation, sim_path)`
  - Updated imports: removed `SimulationNotFoundError`, added `load_simulation`

- **tests/integration/test_skeleton.py**:
  - Removed `test_run_tick_simulation_not_found` (responsibility moved to CLI)
  - Updated all `run_tick()` calls to use new signature `run_tick(simulation, sim_path)`
  - Updated imports: removed `SimulationNotFoundError`
  - Updated `test_run_command_success`: removed check for completion message (message was intentionally removed from CLI)

### Specifications

- **docs/specs/core_config.md**:
  - Updated ConsoleOutputConfig (removed enabled)
  - Updated TelegramOutputConfig (added new fields)
  - Updated config.toml example
  - Added documentation for resolve_output() method

- **docs/specs/core_runner.md**:
  - Updated run_tick signature to `run_tick(simulation: Simulation, sim_path: Path)`
  - Updated tick execution flow (simulation received from CLI, not loaded by runner)
  - Updated usage examples and error handling
  - Removed test_run_tick_simulation_not_found from test coverage

- **docs/specs/core_cli.md**:
  - Updated run command behavior (6 steps including loading simulation before narrators)
  - Updated _run_tick code example

### Backup Files Created

- `src/config_backup_TS-BACKLOG-005-CONFIG-001.py`
- `src/cli_backup_TS-BACKLOG-005-CONFIG-001.py`
- `src/runner_backup_TS-BACKLOG-005-CONFIG-001.py`
- `tests/unit/test_config_backup_TS-BACKLOG-005-CONFIG-001.py`
- `tests/unit/test_runner_backup_TS-BACKLOG-005-CONFIG-001.py`
- `tests/integration/test_skeleton_backup_TS-BACKLOG-005-CONFIG-001.py`

## Tests

- **Result**: PASS (500 tests passed)
- **Existing tests modified**:
  - test_config.py: Updated to remove console.enabled, add telegram fields tests
  - test_runner.py: Updated all run_tick calls to new signature
  - test_skeleton.py: Updated all run_tick calls to new signature
- **New tests added**:
  - TestResolveOutput: 5 tests for resolve_output method
  - TestTelegramOutputConfig: Tests for new telegram fields

## Quality Checks

- **ruff check**: PASS
- **ruff format**: PASS
- **mypy**: PASS (23 source files, excluding backups)

## Issues Encountered

None.

## Next Steps

None - task complete. Infrastructure is now ready for TelegramNarrator implementation in subsequent tasks.

## Commit Proposal

```
feat(config): add resolve_output for simulation-specific output config

- Remove unused console.enabled field from ConsoleOutputConfig
- Add mode, group_intentions, group_narratives to TelegramOutputConfig
- Add Config.resolve_output() for merging config defaults with simulation overrides
- Change TickRunner.run_tick signature to receive simulation and sim_path
- Move simulation loading from runner to CLI for output config resolution
- Update all tests for new run_tick signature
```

## Specs Updated

- docs/specs/core_config.md
- docs/specs/core_runner.md
- docs/specs/core_cli.md
