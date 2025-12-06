# phase_2a.md

## Status: READY

Phase 2a resolves scenes in each location — the Game Master (arbiter) determines
what happens when characters with intentions interact. Processes all locations
in parallel via batch execution, handles failures with fallback that preserves
current state.

---

## Public API

### CharacterUpdate

Pydantic model for single character's update from arbiter.

```python
class CharacterUpdate(BaseModel):
    location: str
    internal_state: str
    external_intent: str
    memory_entry: str = Field(..., min_length=1)
```

### LocationUpdate

Pydantic model for location state update.

```python
class LocationUpdate(BaseModel):
    moment: str | None = None
    description: str | None = None
```

### MasterOutput

Pydantic model for LLM structured output — complete arbiter decision for one location.

```python
class MasterOutput(BaseModel):
    tick: int
    location_id: str
    characters: dict[str, CharacterUpdate]
    location: LocationUpdate
```

Corresponds to `src/schemas/Master.schema.json`.

### execute(simulation, config, llm_client, intentions) -> PhaseResult

Main entry point for Phase 2a.

- **Input**:
  - simulation (Simulation) — current simulation state
  - config (Config) — application configuration
  - llm_client (LLMClient) — client for LLM requests
  - intentions (dict[str, str]) — character intentions from Phase 1 (char_id → intention string)
- **Returns**: PhaseResult with:
  - success: True (always, due to fallback strategy)
  - data: dict[str, MasterOutput] — mapping location_id → arbiter result
- **Side effects**:
  - Logs warning for each fallback
  - Accumulates usage in location entities via llm_client

---

## Data Flow

### Input

- **simulation.characters**: dict[str, Character] — all characters
- **simulation.locations**: dict[str, Location] — all locations
- **intentions**: dict[str, str] — character_id → intention string
- **config**: Config — for PromptRenderer initialization
- **llm_client**: LLMClient — configured for Phase 2a

### Context Assembly (per location)

| Template Variable | Source | Notes |
|-------------------|--------|-------|
| location | Location | Full: identity, state, connections |
| characters | list[Character] | Characters currently in this location |
| intentions | dict[str, str] | Intentions of characters in this location only |
| simulation | Simulation | For current_tick |

### Output

- **dict[str, MasterOutput]** — location_id → arbiter result
- Every location gets an entry (success or fallback)

### Validation

- Input: Pydantic models from Storage (already validated)
- Output: Structured Output guarantees valid MasterOutput

---

## LLM Integration

### Prompts

- **System**: `phase2a_resolution_system.md`
- **User**: `phase2a_resolution_user.md`

Resolution: simulation override → default (via PromptRenderer).

### Schema

`MasterOutput` — tick, location_id, characters dict, location update.

### Batch Execution

All locations processed in parallel via `LLMClient.create_batch()`.

### Entity Key Format

`"resolution:{location_id}"` — for response chain management.

---

## Fallback Strategy

When LLM fails for a location (all retries exhausted):

1. Return fallback MasterOutput:
   - Characters remain in current location
   - States unchanged (copy from current)
   - memory_entry = "[No resolution — simulation continues]"
   - location.moment = None, location.description = None
2. Log warning: `logger.warning("Phase 2a: %s fallback (%s: %s)", loc_id, error_type, error)`

Fallback creation:

```python
def _create_fallback(
    simulation: Simulation,
    loc_id: str,
    chars_here: dict[str, Character],
) -> MasterOutput:
    char_updates = {}
    for char_id, char in chars_here.items():
        char_updates[char_id] = CharacterUpdate(
            location=char.state.location,
            internal_state=char.state.internal_state or "",
            external_intent=char.state.external_intent or "",
            memory_entry="[No resolution — simulation continues]",
        )
    return MasterOutput(
        tick=simulation.current_tick,
        location_id=loc_id,
        characters=char_updates,
        location=LocationUpdate(moment=None, description=None),
    )
```

---

## Algorithm

```
1. Create PromptRenderer with simulation path
2. Group characters by location
3. For each location:
   a. Find characters in this location
   b. Extract their intentions from input dict
   c. Render system prompt (world context in template)
   d. Render user prompt with location, characters, intentions
   e. Create LLMRequest with entity_key="resolution:{loc_id}"
4. Execute batch via llm_client.create_batch()
5. Process results:
   - Success → use MasterOutput
   - LLMError → create fallback + warning log
6. Return PhaseResult(success=True, data=results)
```

---

## Dependencies

- **Standard Library**: logging
- **External**: pydantic>=2.0
- **Internal**:
  - src.config.Config
  - src.utils.storage.Simulation, Character, Location
  - src.utils.llm.LLMClient, LLMRequest
  - src.utils.llm_errors.LLMError
  - src.utils.prompts.PromptRenderer
  - src.phases.common.PhaseResult

---

## File Structure

```
src/phases/
├── __init__.py
├── common.py          # PhaseResult
├── phase1.py          # IntentionResponse, execute()
└── phase2a.py         # MasterOutput, CharacterUpdate, LocationUpdate, execute()
```

---

## Usage Examples

### Basic Execution

```python
from src.config import Config
from src.utils.storage import load_simulation
from src.utils.llm import LLMClient
from src.utils.llm_adapters.openai import OpenAIAdapter
from src.phases.phase1 import execute as execute_phase1
from src.phases.phase2a import execute as execute_phase2a

config = Config.load()
simulation = load_simulation(Path("simulations/demo-sim"))

# Phase 1 first
adapter1 = OpenAIAdapter(config.phase1)
llm_client1 = LLMClient(adapter=adapter1, entities=[...], default_depth=...)
result1 = await execute_phase1(simulation, config, llm_client1)

# Extract intention strings
intentions = {char_id: resp.intention for char_id, resp in result1.data.items()}

# Phase 2a
adapter2a = OpenAIAdapter(config.phase2a)
loc_entities = [loc.model_dump() for loc in simulation.locations.values()]
llm_client2a = LLMClient(adapter=adapter2a, entities=loc_entities, default_depth=...)

result2a = await execute_phase2a(simulation, config, llm_client2a, intentions)

# result2a.data = {
#     "common": MasterOutput(tick=0, location_id="common", ...),
#     "observatory": MasterOutput(tick=0, location_id="observatory", ...),
# }
```

### Accessing Results

```python
result = await execute_phase2a(simulation, config, llm_client, intentions)

for loc_id, master in result.data.items():
    print(f"Location: {loc_id}")
    for char_id, update in master.characters.items():
        print(f"  {char_id}: {update.memory_entry}")
```

---

## Error Handling

### Exit Codes

Phase 2a does not exit directly. Returns PhaseResult, Runner handles exit codes.

### Failure Modes

| Situation | Handling |
|-----------|----------|
| LLM timeout (after retries) | Fallback MasterOutput |
| LLM rate limit (after retries) | Fallback MasterOutput |
| LLM refusal | Fallback MasterOutput |
| LLM incomplete response | Fallback MasterOutput |
| Prompt template not found | Exception propagates to Runner |
| Prompt render error | Exception propagates to Runner |

### Partial Failure

If some locations succeed and some fail:
- Successful locations get real arbiter decisions
- Failed locations get fallback
- Phase returns success=True (simulation continues)

---

## Test Coverage

### Unit Tests (tests/unit/test_phase2a.py)

**Pydantic Models:**
- test_character_update_creation
- test_character_update_memory_entry_required
- test_location_update_optional_fields
- test_master_output_creation
- test_master_output_empty_characters (valid for empty location)

**Context Assembly:**
- test_group_characters_by_location
- test_extract_intentions_for_location
- test_empty_location_no_intentions

**Batch Execution:**
- test_execute_single_location — one location, one character
- test_execute_multiple_locations — parallel processing
- test_execute_empty_location — location with no characters
- test_execute_creates_correct_requests — entity_key format check

**Fallback:**
- test_execute_partial_failure_fallback — mix success/fallback
- test_execute_all_failure_fallback — all locations fallback
- test_fallback_logs_warning — logger.warning called
- test_fallback_preserves_current_state — no state changes in fallback

**Result Structure:**
- test_result_has_all_locations
- test_result_success_always_true
- test_result_data_contains_master_output

### Integration Tests (tests/integration/test_phase2_integration.py)

Uses `demo-sim` simulation with real locations and prompts.

**With Real LLM:**
- test_phase2a_real_llm — all locations get valid MasterOutput
- test_phase2a_character_updates_valid — memory_entry not empty
- test_phase2a_respects_world_logic — no impossible movements

Markers: `@pytest.mark.integration`, `@pytest.mark.slow`

Skip condition: `OPENAI_API_KEY` not set

---

## Implementation Notes

### Logging

- DEBUG: context assembly, prompt rendering
- WARNING: fallback (with error details)

Log format (emoji ⚖️):
```
2025.06.05 14:32:10 | WARNING | ⚖️ phase2a: Phase 2a: common fallback (LLMTimeoutError: Timeout after 3 attempts)
```

### Empty Locations

Locations without characters still get processed:
- MasterOutput has empty `characters` dict
- Arbiter can update `location.moment` (world lives on)
- Useful for weather changes, time passing, ambient events

### Character Grouping

Characters grouped by `character.state.location` to build per-location context.
O(n) grouping, then O(1) lookup per location.
