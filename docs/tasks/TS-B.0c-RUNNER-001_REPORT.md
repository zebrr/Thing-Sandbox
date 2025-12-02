# Task TS-B.0c-RUNNER-001 Completion Report

## Summary

Assembled the skeleton system — implemented TickRunner, CLI, and ConsoleNarrator so that running `python -m src.cli run demo-sim` outputs hardcoded narrative to console and increments `current_tick` from 0 to 1.

## Changes Made

### New Files

- `src/runner.py`: TickRunner implementation
  - `SimulationBusyError` exception for status == "running"
  - `PhaseError` exception for phase failures
  - `TickResult` dataclass with `location_names` field (as discussed)
  - `TickRunner` class with `run_tick(sim_id)` async method
  - Full tick execution flow: load → validate → execute phases → save → narrate

- `src/narrators.py`: Narrator protocol + ConsoleNarrator
  - `Narrator` Protocol with `output(result)` method
  - `ConsoleNarrator` with box-drawing formatted output
  - UTF-8 encoding handling for Windows compatibility
  - Empty narrative marker: `[No narrative]`

- `src/cli.py`: Typer CLI with `run` and `status` commands
  - `run <sim-id>`: executes one tick via TickRunner
  - `status <sim-id>`: displays simulation info
  - Exception → exit code mapping per spec

- `tests/integration/test_skeleton.py`: 9 integration tests
  - `test_run_tick_increments_current_tick`
  - `test_run_tick_returns_narratives`
  - `test_run_tick_simulation_not_found`
  - `test_run_tick_calls_narrators`
  - `test_status_command_output`
  - `test_status_command_not_found`
  - `test_console_narrator_output`
  - `test_run_command_success`
  - `test_run_command_not_found`

### Design Decisions

1. **Storage functions vs class**: Used `load_simulation()` and `save_simulation()` functions directly instead of a Storage class (as clarified in discussion)

2. **TickResult.location_names**: Added `location_names: dict[str, str]` field to TickResult so ConsoleNarrator can display human-readable location names

3. **Empty narratives**: All locations are printed with `[No narrative]` marker if narrative is empty (as clarified in discussion)

4. **Windows encoding**: Added UTF-8 reconfiguration and `errors="replace"` fallback to handle Cyrillic characters in demo-sim

5. **Sequence vs list**: Used `Sequence[Narrator]` for covariance (mypy requirement)

## Tests

- Result: **PASS**
- Existing tests modified: None
- New tests added: 9 tests in `tests/integration/test_skeleton.py`
- Total tests: 222 passed

## Quality Checks

- ruff check: **PASS**
- ruff format: **PASS**
- mypy: **PASS**

## Manual Verification

```bash
python -m src.cli status demo-sim
# demo-sim: tick 0, 2 characters, 2 locations, status: paused

python -m src.cli run demo-sim
# ═══════════════════════════════════════════
# TICK 1
# ═══════════════════════════════════════════
#
# --- Песчаная яма Хорселла ---
# [Stub] Silence hangs over Песчаная яма Хорселла.
#
# --- Уокинг-коммон ---
# [Stub] Silence hangs over Уокинг-коммон.
#
# ═══════════════════════════════════════════
# [demo-sim] Tick 1 completed.

python -m src.cli run nonexistent-sim
# Simulation 'nonexistent-sim' not found
# Exit code: 2
```

## Issues Encountered

1. **Windows encoding**: Initial ConsoleNarrator failed on Russian location names due to Windows console encoding. Fixed by adding stdout UTF-8 reconfiguration and character replacement fallback.

## Next Steps

None — skeleton complete, ready for Phase 1 implementation (B.1b).

## Commit Proposal

`feat: add skeleton system (Runner + CLI + Narrators)`

## Specs Updated

- `docs/specs/core_runner.md`: NOT_STARTED → READY
  - Updated TickResult with `location_names` field
  - Updated constructor signature (removed Storage parameter)
  - Updated storage function references

- `docs/specs/core_cli.md`: NOT_STARTED → READY

- `docs/specs/core_narrators.md`: NOT_STARTED → READY
  - Updated empty narrative behavior
  - Updated encoding handling notes
  - Added `location_names` to usage example

## Deliverables Checklist

- [x] `src/runner.py` — TickRunner implementation
- [x] `src/narrators.py` — Narrator protocol + ConsoleNarrator
- [x] `src/cli.py` — Typer CLI with `run` and `status` commands
- [x] `tests/integration/test_skeleton.py` — E2E tests
- [x] Specs updated to READY status
- [x] All quality checks pass
- [x] Report: `docs/tasks/TS-B.0c-RUNNER-001_REPORT.md`
