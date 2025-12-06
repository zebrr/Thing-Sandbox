# Task TS-B.3b-PHASE2-001 Completion Report

## Summary
Implemented Phase 2a (Arbiter) and Phase 2b (Narrative) modules, replacing stub implementations with full LLM-powered functionality. Updated runner.py to pass intentions and master_results between phases, wrote comprehensive unit tests and integration tests.

**Key Design Decision**: Changed `MasterOutput.characters` from `dict[str, CharacterUpdate]` to `list[CharacterUpdate]` because OpenAI Structured Outputs does not support dicts with dynamic keys. Added `characters_dict` property for convenient dict-style access.

## Changes Made

### Core Implementation

- **`src/phases/phase2a.py`**: Full implementation replacing stub
  - Added Pydantic models: `CharacterUpdate`, `LocationUpdate`, `MasterOutput`
  - Added `_group_by_location()` helper to group characters by location
  - Added `_create_fallback()` for LLM failure fallback
  - Updated `execute()` signature to accept `intentions: dict[str, str]`
  - Batch execution with per-location LLM requests using `entity_key="resolution:{loc_id}"`
  - `CharacterUpdate.memory_entry` has `Field(..., min_length=1)` validation

- **`src/phases/phase2b.py`**: Full implementation replacing stub
  - Added Pydantic model: `NarrativeResponse` with `Field(..., min_length=1)`
  - Added `_group_by_location()` helper
  - Updated `execute()` signature to accept `master_results` and `intentions`
  - Batch execution with `entity_key="narrative:{loc_id}"`
  - Fallback narrative: `"[Silence in the location]"`
  - Added import of `LocationUpdate` for empty MasterOutput creation

- **`src/phases/__init__.py`**: Added export for `NarrativeResponse`

- **`src/runner.py`**: Updated `_execute_phases()` method
  - Extract `intentions_str` from Phase 1 results
  - Pass `intentions_str` to `execute_phase2a()`
  - Create separate LLM client for Phase 2b
  - Pass `result2a.data` and `intentions_str` to `execute_phase2b()`
  - Extract narratives from `NarrativeResponse.narrative` field

### Test Updates

- **`tests/unit/test_runner.py`**: Updated mock functions
  - `mock_phase2a()` now accepts 4 parameters
  - `mock_phase2b()` now accepts 5 parameters
  - Mock returns use `MagicMock(narrative="...")` for proper attribute access

- **`tests/unit/test_phases_stub.py`**: Removed obsolete stub tests
  - Removed 8 tests that were specific to stub implementations
  - Updated `test_phase3_applies_results` to create mock master_results directly

### New Test Files

- **`tests/unit/test_phase2a.py`**: ~20 unit tests covering:
  - Pydantic models (CharacterUpdate, LocationUpdate, MasterOutput)
  - `_group_by_location()` helper
  - `_create_fallback()` helper
  - Context building, batch execution, fallback handling, result structure

- **`tests/unit/test_phase2b.py`**: ~20 unit tests covering:
  - NarrativeResponse model
  - Context building (location_before, characters_before, master_result, intentions)
  - Batch execution, fallback handling, result structure
  - Missing MasterOutput handling

- **`tests/integration/test_phase2_integration.py`**: Integration tests with real LLM
  - `TestPhase2aIntegration`: real LLM tests for Phase 2a
  - `TestPhase2bIntegration`: real LLM tests for Phase 2b
  - `TestPhase2FullChain`: Phase 1 -> 2a -> 2b chain test, usage tracking test

## Tests
- Result: PASS (all tests)
- Unit tests: 401 passed
- Integration tests: 38 passed (including real LLM tests for Phase 2a/2b)
- Existing tests modified: `test_runner.py`, `test_phases_stub.py`, `test_skeleton.py`, `test_phase3.py`
- New tests added: `test_phase2a.py` (20 tests), `test_phase2b.py` (20 tests), `test_phase2_integration.py` (6 tests)

## Quality Checks
- ruff check: PASS
- ruff format: PASS
- mypy: PASS

## Issues Encountered
1. **OpenAI Structured Outputs limitation**: Does not support dicts with dynamic keys (`additionalProperties`). Changed `MasterOutput.characters` from `dict[str, CharacterUpdate]` to `list[CharacterUpdate]` and added `characters_dict` property.
2. **Jinja2 template updates**: Updated all phase2b templates to use `master_result.characters_dict[char.identity.id]` instead of `master_result.characters[char.identity.id]`.
3. **Bug in phase2b.py**: Initial implementation used `MasterOutput.model_fields["location"].default` which returns `PydanticUndefined`. Fixed by using `LocationUpdate()` directly.
4. **Obsolete stub tests**: 8 tests in `test_phases_stub.py` tested stub-specific behavior. Removed them as they're now covered by proper unit tests.
5. **Long lines in test files**: Fixed E501 errors by breaking long function calls across multiple lines.

## Files Modified (Template Updates)
- `src/prompts/phase2b_narrative_user.md`: Updated to use `characters_dict`
- `simulations/demo-sim/prompts/phase2b_narrative_user.md`: Updated to use `characters_dict`
- `simulations/_templates/demo-sim/prompts/phase2b_narrative_user.md`: Updated to use `characters_dict`

## Next Steps
- Phase 4 still uses stub implementation

## Commit Proposal
`feat: implement Phase 2a (Arbiter) and Phase 2b (Narrative)`

## Specs Updated
None - specifications were already complete and accurate
