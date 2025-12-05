# Task TS-B.1b-PHASE1-001 Completion Report

## Summary

Implemented Phase 1 (Character Intentions) — replaced the stub with real LLM-based intention generation. Each character now receives context (identity, state, memory, location, others present) and the LLM generates an intention for what they want to do this tick.

## Changes Made

### src/phases/phase1.py
- Replaced stub with full implementation
- Added `IntentionResponse` Pydantic model (corresponds to IntentionResponse.schema.json)
- Added `_group_by_location()` helper for efficient "others" lookup
- Implemented `execute()` with:
  - Location validation — invalid location → immediate fallback to idle (no LLM call)
  - PromptRenderer initialization with simulation path for overrides
  - Context assembly (character, location, others in same location)
  - System and user prompt rendering
  - LLM batch execution via `llm_client.create_batch()` (only for valid characters)
  - Fallback handling: LLMError → "idle" with warning log + console message
  - Always returns `success=True` (fallback strategy)

### tests/unit/test_phase1.py (NEW)
- 26 unit tests covering:
  - IntentionResponse model creation (including Unicode)
  - `_group_by_location()` helper (5 tests)
  - Context building (others list, prompt rendering)
  - Batch execution (all success, partial failure, all failure)
  - Fallback handling (logging, console output)
  - Invalid location handling (immediate fallback, no LLM call)
  - Result structure (all characters present, success always True)

### tests/integration/test_phase1_integration.py (REWRITTEN)
- 3 integration tests with real LLM using `demo-sim`:
  - `test_generate_intention_real_llm` — all characters get non-idle intentions (PASS)
  - `test_intention_language_matches_simulation` — Russian prompts → Cyrillic output (PASS)
  - `test_multiple_characters_unique_intentions` — unique intentions per character (PASS)

### tests/unit/test_phases_stub.py
- Updated Phase 1 tests to use mock LLM client (no longer stub tests)
- Added `mock_llm_client` fixture
- Tests now use `patch("src.phases.phase1.PromptRenderer")`

### tests/unit/test_cli.py
- Fixed bug: changed `result.stdout` to `result.output` for error assertions (errors go to stderr)

### docs/specs/phase_1.md
- Changed status from `NOT_STARTED` to `READY`
- Updated algorithm to include location validation step
- Updated failure modes table with "Invalid location" row
- Updated test coverage section with actual test names

## Tests

- Result: **PASS**
- Unit tests: 263 passed (including 26 new Phase 1 tests)
- Integration tests: 3 passed (with real OpenAI API using demo-sim)
- Existing tests modified:
  - `tests/unit/test_phases_stub.py` (2 tests updated for Phase 1)
  - `tests/unit/test_cli.py` (2 tests fixed: stdout → output)
- New tests added:
  - `tests/unit/test_phase1.py` (26 tests)
  - `tests/integration/test_phase1_integration.py` (3 tests)

## Quality Checks

- ruff check: **PASS**
- ruff format: **PASS**
- mypy: **PASS** (no issues)

## Issues Encountered

1. **test_phases_stub.py failures**: Old stub tests passed `None` as `llm_client`, which no longer works. Fixed by adding mock LLM client and patching PromptRenderer.

2. **test_cli.py failures**: Tests checked `result.stdout` but CLI outputs errors to stderr via `err=True`. Fixed by using `result.output` which captures both.

3. **Invalid location handling**: Original implementation used fallback to first available location, which would give character wrong context. Fixed to immediately fallback to idle without LLM call.

4. **Integration tests with fake data**: Original tests created fake characters in memory but sim_path pointed to nonexistent folder. Refactored to use `demo-sim` for consistent testing with real prompts and characters.

## Next Steps

None — task complete.

## Commit Proposal

`feat: implement Phase 1 (character intentions) with LLM integration`

## Specs Updated

- `docs/specs/phase_1.md` — status READY, algorithm updated, test coverage updated
