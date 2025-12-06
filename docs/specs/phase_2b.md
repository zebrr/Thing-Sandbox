# phase_2b.md

## Status: READY

Phase 2b generates narrative text for each location — transforms arbiter decisions
into human-readable prose for the observer log. Processes all locations in parallel,
handles failures with placeholder text.

---

## Public API

### NarrativeResponse

Pydantic model for LLM structured output.

```python
class NarrativeResponse(BaseModel):
    narrative: str = Field(..., min_length=1)
```

Corresponds to `src/schemas/NarrativeResponse.schema.json`.

### execute(simulation, config, llm_client, master_results, intentions) -> PhaseResult

Main entry point for Phase 2b.

- **Input**:
  - simulation (Simulation) — current simulation state (BEFORE Phase 3 applies changes)
  - config (Config) — application configuration
  - llm_client (LLMClient) — client for LLM requests
  - master_results (dict[str, MasterOutput]) — arbiter decisions from Phase 2a
  - intentions (dict[str, str]) — character intentions from Phase 1 (for context)
- **Returns**: PhaseResult with:
  - success: True (always, due to fallback strategy)
  - data: dict[str, NarrativeResponse] — mapping location_id → narrative
- **Side effects**:
  - Logs warning for each fallback
  - Accumulates usage in location entities via llm_client

---

## Data Flow

### Input

- **simulation.characters**: dict[str, Character] — characters BEFORE changes
- **simulation.locations**: dict[str, Location] — locations BEFORE changes
- **master_results**: dict[str, MasterOutput] — arbiter decisions (what will happen)
- **intentions**: dict[str, str] — character intentions (what they wanted)
- **config**: Config — for PromptRenderer initialization
- **llm_client**: LLMClient — configured for Phase 2b

### Context Assembly (per location)

| Template Variable | Source | Notes |
|-------------------|--------|-------|
| location_before | Location | State BEFORE arbiter changes |
| characters_before | list[Character] | Characters in location BEFORE |
| master_result | MasterOutput | Arbiter decision for this location |
| intentions | dict[str, str] | Intentions of characters in this location |

### Output

- **dict[str, NarrativeResponse]** — location_id → narrative
- Every location gets an entry (success or fallback)

### Validation

- Input: Pydantic models from previous phases
- Output: Structured Output guarantees valid NarrativeResponse

---

## LLM Integration

### Prompts

- **System**: `phase2b_narrative_system.md`
- **User**: `phase2b_narrative_user.md`

Resolution: simulation override → default (via PromptRenderer).

### Schema

`NarrativeResponse` — single field `narrative: str`.

### Batch Execution

All locations processed in parallel via `LLMClient.create_batch()`.

### Entity Key Format

`"narrative:{location_id}"` — for response chain management.

---

## Fallback Strategy

When LLM fails for a location (all retries exhausted):

1. Return `NarrativeResponse(narrative="[Silence in the location]")`
2. Log warning: `logger.warning("Phase 2b: %s fallback (%s: %s)", loc_id, error_type, error)`

**Note**: Fallback text is intentionally minimal and bracketed to indicate
technical failure rather than narrative choice.

---

## Algorithm

```
1. Create PromptRenderer with simulation path
2. Group characters by location (for "before" state)
3. For each location:
   a. Get location state (before changes)
   b. Find characters in this location (before changes)
   c. Get MasterOutput for this location from master_results
   d. Extract intentions for characters in this location
   e. Render system prompt (world context, style in template)
   f. Render user prompt with before state + arbiter decision
   g. Create LLMRequest with entity_key="narrative:{loc_id}"
4. Execute batch via llm_client.create_batch()
5. Process results:
   - Success → use NarrativeResponse
   - LLMError → fallback + warning log
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
  - src.phases.phase2a.MasterOutput

---

## File Structure

```
src/phases/
├── __init__.py
├── common.py          # PhaseResult
├── phase1.py          # IntentionResponse, execute()
├── phase2a.py         # MasterOutput, execute()
└── phase2b.py         # NarrativeResponse, execute()
```

---

## Usage Examples

### Basic Execution

```python
from src.phases.phase2a import execute as execute_phase2a
from src.phases.phase2b import execute as execute_phase2b, NarrativeResponse

# After Phase 2a
result2a = await execute_phase2a(simulation, config, llm_client2a, intentions)

# Phase 2b
adapter2b = OpenAIAdapter(config.phase2b)
loc_entities = [loc.model_dump() for loc in simulation.locations.values()]
llm_client2b = LLMClient(adapter=adapter2b, entities=loc_entities, default_depth=...)

result2b = await execute_phase2b(
    simulation, 
    config, 
    llm_client2b, 
    result2a.data,  # MasterOutput dict
    intentions,
)

# result2b.data = {
#     "common": NarrativeResponse(narrative="The morning sun cast long shadows..."),
#     "observatory": NarrativeResponse(narrative="Ogilvy peered through the telescope..."),
# }
```

### Accessing Narratives

```python
result = await execute_phase2b(simulation, config, llm_client, master_results, intentions)

for loc_id, narrative_resp in result.data.items():
    print(f"=== {loc_id} ===")
    print(narrative_resp.narrative)
    print()
```

---

## Error Handling

### Exit Codes

Phase 2b does not exit directly. Returns PhaseResult, Runner handles exit codes.

### Failure Modes

| Situation | Handling |
|-----------|----------|
| LLM timeout (after retries) | Fallback narrative |
| LLM rate limit (after retries) | Fallback narrative |
| LLM refusal | Fallback narrative |
| LLM incomplete response | Fallback narrative |
| Missing MasterOutput for location | Use empty MasterOutput, log warning |
| Prompt template not found | Exception propagates to Runner |
| Prompt render error | Exception propagates to Runner |

### Partial Failure

If some locations succeed and some fail:
- Successful locations get real narratives
- Failed locations get fallback text
- Phase returns success=True (simulation continues)

---

## Test Coverage

### Unit Tests (tests/unit/test_phase2b.py)

**NarrativeResponse:**
- test_narrative_response_creation
- test_narrative_response_min_length — empty string rejected
- test_narrative_response_unicode — Cyrillic support

**Context Assembly:**
- test_build_context_with_characters
- test_build_context_empty_location
- test_build_context_includes_master_result
- test_build_context_includes_intentions

**Batch Execution:**
- test_execute_single_location
- test_execute_multiple_locations
- test_execute_empty_location — narrative for empty world
- test_execute_creates_correct_requests — entity_key format

**Fallback:**
- test_execute_partial_failure_fallback
- test_execute_all_failure_fallback
- test_fallback_logs_warning
- test_fallback_text_is_bracketed

**Result Structure:**
- test_result_has_all_locations
- test_result_success_always_true
- test_result_data_contains_narrative_response

### Integration Tests (tests/integration/test_phase2_integration.py)

Uses `demo-sim` simulation with real locations and prompts.

**With Real LLM:**
- test_phase2b_real_llm — generates readable narrative
- test_phase2b_narrative_not_empty — all narratives have content
- test_phase2b_reflects_arbiter_decisions — narrative mentions events from MasterOutput

Markers: `@pytest.mark.integration`, `@pytest.mark.slow`

Skip condition: `OPENAI_API_KEY` not set

---

## Implementation Notes

### Logging

- DEBUG: context assembly, prompt rendering
- WARNING: fallback (with error details)

Log format (emoji 📖):
```
2025.06.05 14:32:12 | WARNING | 📖 phase2b: Phase 2b: common fallback (LLMRefusalError: Content policy)
```

### Before vs After State

Phase 2b receives simulation state BEFORE Phase 3 applies changes.
This is intentional — narrator describes the transition:
- "Before" state in simulation
- "After" state in MasterOutput

The prompt template uses both to show what changed.

### Empty Locations

Locations without characters still get narratives:
- Narrator describes the world living on
- Weather, time passing, ambient sounds
- Can reference location.moment changes from arbiter

### Relationship with Phase 3

Phase 2b runs BEFORE Phase 3:
```
Phase 1 → Phase 2a → Phase 2b → Phase 3 → Phase 4
```

This order is important because Phase 2b needs the "before" state
to describe the transition. Phase 3 then applies the changes.
