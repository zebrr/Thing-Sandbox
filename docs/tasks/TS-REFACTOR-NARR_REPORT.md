# Task TS-REFACTOR-NARR Completion Report

## Summary

Extended the Narrator protocol with two new lifecycle methods (`on_tick_start`, `on_phase_complete`) to support tick progress feedback during execution. Added notification helper methods to TickRunner that call narrators at appropriate points in the tick lifecycle.

## Changes Made

### Modified Files

- **src/narrators.py**:
  - Added `PhaseData` import (via TYPE_CHECKING)
  - Extended `Narrator` protocol with `on_tick_start` and `on_phase_complete` methods
  - Added no-op implementations to `ConsoleNarrator` for both methods

- **src/runner.py**:
  - Added `_notify_tick_start(sim_id, tick_number)` helper method
  - Added `_notify_phase_complete(phase_name, phase_data)` helper method
  - Added `_notify_tick_start` call after status set to "running" (step 3b)
  - Added `_notify_phase_complete` calls after each phase (5 calls total: phase1, phase2a, phase2b, phase3, phase4)

- **tests/unit/test_narrators.py**:
  - Added `MockPhaseData` dataclass for testing without runner imports
  - Updated `test_custom_narrator_satisfies_protocol` to include new methods
  - Added `test_console_narrator_on_tick_start_noop`
  - Added `test_console_narrator_on_phase_complete_noop`

- **tests/unit/test_runner.py**:
  - Added `TestNarratorLifecycleNotifications` class with 4 tests:
    - `test_runner_calls_on_tick_start`
    - `test_runner_calls_on_phase_complete_for_each_phase`
    - `test_runner_narrator_on_tick_start_error_isolated`
    - `test_runner_narrator_on_phase_complete_error_isolated`

- **docs/specs/core_narrators.md**:
  - Added new protocol methods documentation
  - Added `ConsoleNarrator.on_tick_start` and `on_phase_complete` docs
  - Updated Dependencies section (PhaseData added)
  - Updated Test Coverage section

- **docs/specs/core_runner.md**:
  - Updated Tick Execution Flow sequence with narrator notifications
  - Added `_notify_tick_start` and `_notify_phase_complete` to Internal Methods
  - Updated Test Coverage section with new tests

## Tests

- Result: **PASS**
- Unit tests: 493 passed (was 487, added 6 new)
- New tests:
  - `test_console_narrator_on_tick_start_noop`
  - `test_console_narrator_on_phase_complete_noop`
  - `test_runner_calls_on_tick_start`
  - `test_runner_calls_on_phase_complete_for_each_phase`
  - `test_runner_narrator_on_tick_start_error_isolated`
  - `test_runner_narrator_on_phase_complete_error_isolated`
- Existing tests modified: `test_custom_narrator_satisfies_protocol` (added new method checks)

## Quality Checks

- ruff check: **PASS**
- ruff format: **PASS**
- mypy: **PASS**

## Issues Encountered

None.

## Next Steps

None. The protocol extension is ready for use by future narrators (e.g., TelegramNarrator progress updates).

## Commit Proposal

```
feat(narrators): extend Narrator protocol with tick lifecycle events
```

## Specs Updated

- docs/specs/core_narrators.md
- docs/specs/core_runner.md
