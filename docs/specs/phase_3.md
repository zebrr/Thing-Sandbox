# phase_3.md

## Status: READY

Phase 3 applies arbitration results to simulation state. Pure mechanics, no LLM.
Takes MasterOutput from Phase 2a, updates characters (location, state) and locations
(moment, description), collects memory entries for Phase 4.

---

## Public API

### execute(simulation, config, master_results) -> PhaseResult

Main entry point for Phase 3.

- **Input**:
  - simulation (Simulation) — current simulation state (mutated in place)
  - config (Config) — application configuration (unused, for signature consistency)
  - master_results (dict[str, MasterOutput]) — location_id → arbitration result
- **Returns**: PhaseResult with:
  - success: True (always, invalid data is skipped with warnings)
  - data: dict with key "pending_memories" → dict[str, str] (character_id → memory_entry)
- **Side effects**:
  - Mutates simulation.characters[].state (location, internal_state, external_intent)
  - Mutates simulation.locations[].state.moment
  - Mutates simulation.locations[].identity.description
  - Logs warning for invalid data
  - Prints to console for invalid data

---

## Data Flow

### Input: MasterOutput Structure

From Phase 2a, per location:

```python
class CharacterUpdate(BaseModel):
    location: str           # new location (may have moved)
    internal_state: str     # new inner state
    external_intent: str    # new goals
    memory_entry: str       # subjective memory for this tick

class LocationUpdate(BaseModel):
    moment: str | None      # new moment, null = unchanged
    description: str | None # new description, null = unchanged

class MasterOutput(BaseModel):
    tick: int
    location_id: str
    characters: dict[str, CharacterUpdate]  # char_id → update
    location: LocationUpdate
```

Note: `MasterOutput` and related models defined in `phase2a.py`.

### Output

```python
{
    "pending_memories": {
        "ogilvy": "Я подошёл к цилиндру...",
        "henderson": "Записал показания Огилви..."
    }
}
```

Every character mentioned in master_results gets an entry in pending_memories.

---

## Algorithm

```
1. Initialize pending_memories = {}
2. For each (location_id, master_output) in master_results:
   a. Validate location_id exists in simulation.locations
      - If not → warning + print + skip this location
   b. Apply location updates:
      - If moment is not None → update location.state.moment
      - If description is not None → update location.identity.description
   c. For each (char_id, char_update) in master_output.characters:
      i. Validate char_id exists in simulation.characters
         - If not → warning + print + skip this character
      ii. Validate char_update.location exists in simulation.locations
         - If not → warning + print + keep current location
      iii. Update character.state.location (if valid)
      iv. Update character.state.internal_state
      v. Update character.state.external_intent
      vi. Add to pending_memories[char_id] = char_update.memory_entry
3. Return PhaseResult(success=True, data={"pending_memories": pending_memories})
```

---

## Validation & Fallbacks

| Situation | Handling |
|-----------|----------|
| location_id not in simulation.locations | Skip entire location + warning + print |
| char_id not in simulation.characters | Skip character + warning + print |
| char_update.location not in simulation.locations | Keep current location + warning + print |

All fallbacks follow the pattern:
1. Log: `logger.warning(f"Phase 3: {description}")`
2. Print: `print(f"⚠️  Phase 3: {description}")`

### Console Output Format

```
⚠️  Phase 3: unknown location 'mars' in master_results, skipping
⚠️  Phase 3: unknown character 'ghost' in location 'tavern', skipping
⚠️  Phase 3: invalid target location 'nowhere' for character 'bob', keeping current
```

---

## Dependencies

- **Standard Library**: logging
- **External**: None
- **Internal**:
  - src.config.Config
  - src.utils.storage.Simulation, Character, Location
  - src.phases.common.PhaseResult
  - src.phases.phase2a.MasterOutput, CharacterUpdate, LocationUpdate

---

## File Structure

```
src/phases/
├── __init__.py
├── common.py          # PhaseResult
├── phase1.py          # IntentionResponse, execute()
├── phase2a.py         # MasterOutput, CharacterUpdate, LocationUpdate, execute()
├── phase2b.py         # NarrativeResponse, execute()
├── phase3.py          # execute()
└── phase4.py          # SummaryResponse, execute()
```

---

## Related Changes

### runner.py

Update to pass data between phases:

```python
# Before
result2a = await execute_phase2a(simulation, config, None)  # type: ignore
result3 = await execute_phase3(simulation, config, None)    # type: ignore
result4 = await execute_phase4(simulation, config, None)    # type: ignore

# After
result2a = await execute_phase2a(simulation, config, llm_client)
result3 = await execute_phase3(simulation, config, result2a.data)
result4 = await execute_phase4(simulation, config, llm_client, result3.data["pending_memories"])
```

### phase2a.py

Add Pydantic models (stub returns dict matching this structure):

```python
class CharacterUpdate(BaseModel):
    location: str
    internal_state: str
    external_intent: str
    memory_entry: str

class LocationUpdate(BaseModel):
    moment: str | None = None
    description: str | None = None

class MasterOutput(BaseModel):
    tick: int
    location_id: str
    characters: dict[str, CharacterUpdate]
    location: LocationUpdate
```

### phase4.py

Update signature to accept pending_memories:

```python
# Before
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
) -> PhaseResult:

# After
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
    pending_memories: dict[str, str],
) -> PhaseResult:
```

---

## Usage Examples

### Basic Execution

```python
from src.phases.phase3 import execute

# After Phase 2a
result2a = await execute_phase2a(simulation, config, llm_client)

# Phase 3 applies results
result3 = await execute(simulation, config, result2a.data)

# simulation is now mutated
# result3.data["pending_memories"] ready for Phase 4
```

### Inspecting Results

```python
result3 = await execute(simulation, config, master_results)

for char_id, memory in result3.data["pending_memories"].items():
    print(f"{char_id}: {memory[:50]}...")
```

---

## Test Coverage

### Unit Tests (tests/unit/test_phase3.py)

**Character Updates:**
- test_update_character_location — location changes correctly
- test_update_character_internal_state — internal_state updated
- test_update_character_external_intent — external_intent updated
- test_update_multiple_characters — batch update works

**Location Updates:**
- test_update_location_moment — moment changes when not None
- test_update_location_moment_null — moment unchanged when None
- test_update_location_description — description changes when not None
- test_update_location_description_null — description unchanged when None

**Memory Collection:**
- test_collect_memory_entries — all entries in pending_memories
- test_memory_entries_match_characters — correct char_id mapping

**Validation & Fallbacks:**
- test_invalid_location_id_skipped — unknown location in master_results
- test_invalid_char_id_skipped — unknown character in master_results
- test_invalid_target_location_keeps_current — character stays in place
- test_fallback_logs_warning — logger.warning called
- test_fallback_prints_console — print with ⚠️ prefix

**Edge Cases:**
- test_empty_master_results — empty dict returns empty pending_memories
- test_empty_characters_in_location — location with no characters
- test_single_location_single_character — minimal case
- test_multiple_locations — multiple locations processed

**Result Structure:**
- test_result_success_always_true — success=True even with fallbacks
- test_result_data_has_pending_memories — correct key exists
- test_result_pending_memories_type — dict[str, str]

**Mutation:**
- test_simulation_mutated_in_place — original object changed
- test_no_new_characters_created — only existing characters updated
- test_no_new_locations_created — only existing locations updated

---

## Implementation Notes

### No LLM

Phase 3 is pure mechanics. No LLMClient usage, no async operations needed
(but signature is async for consistency with other phases).

### Mutation Strategy

Phase 3 mutates `simulation` directly. This is safe because:
1. Runner holds simulation in memory
2. Disk save happens only after all phases complete
3. If any phase fails, no changes are persisted

### Order of Operations

1. Location updates first (moment, description)
2. Character updates second (may reference updated location state)

This order doesn't matter functionally, but is cleaner conceptually.

### Logging

- DEBUG: each character/location update
- WARNING: validation failures (skipped data)
