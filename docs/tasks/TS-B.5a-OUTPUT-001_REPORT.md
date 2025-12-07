# Task TS-B.5a-OUTPUT-001 Completion Report

## Summary

Implemented foundational output infrastructure for TickLogger: added OutputConfig for output channel control, extended BatchStats with per-request results (including reasoning summaries), and added stats field to PhaseResult for passing LLM statistics from phases to runner.

## Changes Made

### config.toml
- Added `[output.console]` section with `enabled` and `show_narratives` fields
- Added `[output.file]` section with `enabled` field
- Added `[output.telegram]` section with `enabled` and `chat_id` fields

### src/config.py
- Added `ConsoleOutputConfig` model (enabled, show_narratives)
- Added `FileOutputConfig` model (enabled)
- Added `TelegramOutputConfig` model (enabled, chat_id)
- Added `OutputConfig` model composing all three
- Updated `Config.__init__()` with `output` parameter
- Updated `Config.load()` to parse `[output]` section with defaults

### src/utils/llm.py
- Added `RequestResult` dataclass for per-request result tracking:
  - `entity_key: str | None`
  - `success: bool`
  - `usage: ResponseUsage | None`
  - `reasoning_summary: list[str] | None`
  - `error: str | None`
- Extended `BatchStats` with `results: list[RequestResult]` field
- Updated `create_response()` to populate `stats.results` on success
- Updated `_execute_one()` to populate `stats.results` on both success and failure

### src/phases/common.py
- Added `TYPE_CHECKING` import for `BatchStats`
- Added `stats: BatchStats | None = None` field to `PhaseResult`

### src/phases/phase1.py, phase2a.py, phase2b.py, phase4.py
- Updated return statements to include `stats=llm_client.get_last_batch_stats() if llm_client else None`

## Tests

- Result: **PASS** (436 passed, 41 deselected)
- Existing tests modified: None
- New tests added:
  - `test_config.py`: 7 tests for OutputConfig (TestOutputConfig class)
  - `test_llm.py`: 10 tests for RequestResult and BatchStats.results
  - `test_phases_common.py`: 4 tests for PhaseResult.stats

## Quality Checks

- ruff check: **PASS** (All checks passed!)
- ruff format: **PASS** (22 files left unchanged)
- mypy: **PASS** (Success: no issues found in 22 source files)

## Issues Encountered

One test `test_phase4_succeeds_with_no_op` was passing `None` as `llm_client`. Added defensive check `if llm_client else None` to all phase return statements to handle edge case.

## Next Steps

- TS-B.5b: Implement TickLogger to consume BatchStats and write tick logs
- Runner integration: pass PhaseResult.stats to TickLogger after each phase

## Commit Proposal

`feat: add OutputConfig, RequestResult, and PhaseResult.stats for TickLogger foundation`

## Specs Updated

- `docs/specs/core_config.md` — added OutputConfig, ConsoleOutputConfig, FileOutputConfig, TelegramOutputConfig documentation
- `docs/specs/util_llm.md` — added RequestResult, updated BatchStats with results field
- `docs/specs/phase_common.md` — added stats field to PhaseResult
