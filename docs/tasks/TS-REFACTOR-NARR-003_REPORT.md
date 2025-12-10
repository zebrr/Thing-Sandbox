# Task TS-REFACTOR-NARR-003 Completion Report

## Summary

Made lifecycle methods (`on_tick_start`, `on_phase_complete`) of the Narrator protocol async with fire-and-forget pattern. This allows TelegramNarrator to send messages in parallel with phase execution without blocking the simulation.

## Changes Made

### src/narrators.py
- Changed `on_tick_start` and `on_phase_complete` from sync to async in `Narrator` Protocol
- Updated docstrings to describe async behavior and fire-and-forget pattern
- Changed `ConsoleNarrator.on_tick_start` and `ConsoleNarrator.on_phase_complete` to async methods

### src/runner.py
- Added `import asyncio`
- Added constant `NARRATOR_TIMEOUT = 30.0` for timeout on awaiting narrator tasks
- Added instance attribute `_pending_narrator_tasks: list[asyncio.Task[None]]` initialized in `run_tick`
- Changed `_notify_tick_start` to async method that awaits narrator calls directly
- Changed `_notify_phase_complete` to use fire-and-forget pattern:
  - Creates `asyncio.Task` for each narrator via `_safe_phase_complete` wrapper
  - Appends tasks to `_pending_narrator_tasks` list
- Added `_safe_phase_complete` async method to wrap `on_phase_complete` with error handling
- Added `_await_pending_narrator_tasks` async method to await all pending tasks with timeout
- Updated `run_tick` to:
  - Initialize `_pending_narrator_tasks` after status check
  - Await `_notify_tick_start` (fast, no network)
  - Call `_await_pending_narrator_tasks` after `save_simulation` (data safety first)

### tests/unit/test_narrators.py
- Added `@pytest.mark.asyncio` decorator to lifecycle tests
- Changed `on_tick_start` and `on_phase_complete` tests to use `await`
- Updated `CustomNarrator` in protocol test to have async methods

### tests/unit/test_runner.py
- Updated all `MockNarrator` classes to have async `on_tick_start` and `on_phase_complete` methods
- Added new test `test_runner_awaits_pending_tasks_at_end` verifying tasks are awaited before run_tick returns
- Added new test `test_runner_narrator_timeout_doesnt_block` verifying timeout handling

### docs/specs/core_narrators.md
- Updated Protocol definition to show async methods
- Updated method documentation to describe async behavior and fire-and-forget pattern
- Updated "Protocol vs ABC" section with async support note

### docs/specs/core_runner.md
- Added `Constants` section with `NARRATOR_TIMEOUT = 30.0`
- Added `_pending_narrator_tasks` to Internal Attributes
- Updated Tick Execution Flow sequence (steps 3a, 3b, 11b)
- Updated `_notify_tick_start` documentation (now async, awaited)
- Updated `_notify_phase_complete` documentation (fire-and-forget pattern)
- Added `_safe_phase_complete` method documentation
- Added `_await_pending_narrator_tasks` method documentation
- Added new tests to Test Coverage section

## Tests

- Result: PASS
- Existing tests modified: 8 tests updated with async/await
- New tests added:
  - `test_runner_awaits_pending_tasks_at_end`
  - `test_runner_narrator_timeout_doesnt_block`
- Total tests run: 495 passed

## Quality Checks

- ruff check: PASS
- ruff format: PASS (1 file reformatted)
- mypy: PASS (no issues found in 2 source files)

## Issues Encountered

None

## Next Steps

None - ready for TelegramNarrator implementation

## Commit Proposal

`refactor: make narrator lifecycle methods async with fire-and-forget pattern`

## Specs Updated

- `docs/specs/core_narrators.md`
- `docs/specs/core_runner.md`
