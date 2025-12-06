# Task TS-USAGE_REFACTOR-001 Completion Report

## Summary

Implemented full LLM usage tracking pipeline as specified in `docs/Thing' Sandbox LLM Usage Tracking.md`:
- Extended usage format from `total_input_tokens`/`total_output_tokens` to `total_tokens`/`reasoning_tokens`/`cached_tokens`/`total_requests`
- Added `BatchStats` dataclass and `get_last_batch_stats()` method to LLMClient for phase-level logging
- Created separate entity dicts for characters and locations in Runner
- Implemented sync of `_openai` data back to Simulation models via `__pydantic_extra__`
- Implemented aggregation of usage into `simulation._openai`
- Added per-phase and per-tick logging with statistics

## Changes Made

### src/utils/llm.py
- Added `BatchStats` dataclass with fields: `total_tokens`, `reasoning_tokens`, `cached_tokens`, `request_count`, `success_count`, `error_count`
- Modified `_accumulate_usage()` to use new format (`total_tokens` instead of `total_input_tokens`/`total_output_tokens`)
- Added `_last_batch_stats` attribute to `__init__()`
- Added `get_last_batch_stats() -> BatchStats` public method
- Modified `create_batch()` to reset and accumulate batch stats
- Modified `create_response()` to track single-request stats
- Modified `_execute_one()` to accumulate stats on success/error

### src/runner.py
- Added imports: `time`, `Any`, `PhaseConfig`, `BatchStats`
- Replaced `_create_llm_client()` with three methods:
  - `_create_entity_dicts()` - creates `_char_entities` and `_loc_entities`
  - `_create_char_llm_client()` - for phases 1, 4
  - `_create_loc_llm_client()` - for phases 2a, 2b
- Added `_sync_openai_data()` - copies `_openai` from entity dicts to Pydantic models via `__pydantic_extra__`
- Added `_aggregate_simulation_usage()` - sums usage from all entities
- Added `_accumulate_tick_stats()` - adds phase stats to tick totals
- Updated `run_tick()` with timing, stats initialization, sync/aggregate calls, and logging
- Updated `_execute_phases()` with separate clients and per-phase logging

### src/utils/storage.py
- Added `Any` import
- Updated `save_simulation()` to include `__pydantic_extra__` in simulation.json

## Tests

- Unit tests: PASS (360 tests passed in 0.68s)
- Integration tests: PASS (8 tests passed in 63.95s with real OpenAI API)
- Existing tests modified:
  - `tests/unit/test_llm.py`: Updated all usage assertions from old format to new format
  - `tests/integration/test_llm_integration.py`: Updated `test_usage_persisted_in_entity` assertions
- New tests added:
  - `tests/unit/test_llm.py`: Added `TestBatchStats` class with 5 tests:
    - `test_batch_stats_defaults`
    - `test_get_last_batch_stats_initial`
    - `test_get_last_batch_stats_after_batch`
    - `test_get_last_batch_stats_after_create_response`
    - `test_batch_stats_reset_between_calls`
  - `tests/unit/test_runner.py`: Added test classes:
    - `TestSyncOpenaiData`: 3 tests for `_sync_openai_data()`
    - `TestAggregateSimulationUsage`: 2 tests for `_aggregate_simulation_usage()`
  - `tests/unit/test_storage.py`: Added `TestOpenaiRoundtrip`: 1 test for `_openai` persistence

## Quality Checks

- ruff check: PASS
- ruff format: PASS
- mypy: PASS

## Issues Encountered

1. **Roundtrip tests failed** - Initially used `__dict__["_openai"]` but Pydantic's `model_dump()` only includes `__pydantic_extra__`. Fixed by using `__pydantic_extra__` instead.

2. **mypy errors on indexed assignment** - `__pydantic_extra__` has type `dict[str, Any] | None` and mypy can't track narrowing across assignment. Fixed by using conditional pattern with `object.__setattr__()`.

3. **Integration test using old format** - Forgot to update integration test assertions. Fixed by changing to `total_tokens` instead of `total_input_tokens`.

## Integration Test Verification

Integration test `test_usage_persisted_in_entity` confirms all usage parameters are received from real OpenAI API:
- `total_tokens > 0` - verified
- `reasoning_tokens >= 0` - verified (model may or may not use reasoning)
- `cached_tokens >= 0` - verified (caching depends on request patterns)
- `total_requests == 2` - verified (exact count)

## Next Steps

1. Implement Phase 2b with LLM (separate task) - infrastructure is ready

## Commit Proposal

```
feat: implement LLM usage tracking with BatchStats and sync to Simulation

- Add BatchStats dataclass and get_last_batch_stats() to LLMClient
- Extend usage format: total_tokens, reasoning_tokens, cached_tokens
- Create separate entity dicts for characters/locations in Runner
- Sync _openai data back to Simulation via __pydantic_extra__
- Aggregate usage into simulation._openai
- Add per-phase and tick completion logging with statistics
```

## Specs Updated

- `docs/specs/util_llm.md`:
  - Added `get_last_batch_stats() -> BatchStats` to Public API
  - Added `BatchStats` dataclass documentation
  - Updated Chain Storage JSON example with new usage format
  - Updated `_accumulate_usage()` code example

- `docs/specs/core_runner.md`:
  - Added Internal Attributes section
  - Updated Tick Execution Flow sequence
  - Added Internal Methods section with all new methods
  - Updated Dependencies section
  - Updated Logging section with per-phase format
  - Updated Test Coverage section
