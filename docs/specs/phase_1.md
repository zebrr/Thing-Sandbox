# phase_1.md

## Status: NOT_STARTED

Phase 1 generates character intentions — what each character wants to do this tick.
Collects context (identity, state, memory, location, others), renders prompts,
calls LLM via batch execution, handles failures with idle fallback.

---

## Public API

### IntentionResponse

Pydantic model for LLM structured output.

```python
class IntentionResponse(BaseModel):
    intention: str
```

Corresponds to `src/schemas/IntentionResponse.schema.json`.

### execute(simulation, config, llm_client) -> PhaseResult

Main entry point for Phase 1.

- **Input**:
  - simulation (Simulation) — current simulation state with characters and locations
  - config (Config) — application configuration
  - llm_client (LLMClient) — client for LLM requests
- **Returns**: PhaseResult with:
  - success: True (always, due to fallback strategy)
  - data: dict[str, IntentionResponse] — mapping character_id → intention
- **Side effects**:
  - Logs warning for each fallback
  - Prints to console for each fallback
  - Accumulates usage in character entities via llm_client

---

## Data Flow

### Input

- **simulation.characters**: dict[str, Character] — all characters
- **simulation.locations**: dict[str, Location] — all locations
- **config**: Config — for PromptRenderer initialization
- **llm_client**: LLMClient — configured for Phase 1

### Context Assembly (per character)

| Template Variable | Source | Notes |
|-------------------|--------|-------|
| character | Character | Full: identity, state, memory |
| location | Location | Character's current location |
| others | list[CharacterIdentity] | Other characters in same location (identity only) |

### Output

- **dict[str, IntentionResponse]** — character_id → intention response
- Every character gets an entry (success or fallback)

### Validation

- Input: Pydantic models from Storage (already validated)
- Output: Structured Output guarantees valid IntentionResponse

---

## LLM Integration

### Prompts

- **System**: `phase1_intention_system.md`
- **User**: `phase1_intention_user.md`

Resolution: simulation override → default (via PromptRenderer).

### Schema

`IntentionResponse` — single field `intention: str`.

### Batch Execution

All characters processed in parallel via `LLMClient.create_batch()`.

### Entity Key Format

`"intention:{character_id}"` — for response chain management.

---

## Fallback Strategy

When LLM fails for a character (all retries exhausted):

1. Return `IntentionResponse(intention="idle")`
2. Log warning: `logger.warning(f"Phase 1: {char_id} fallback to idle ({error})")`
3. Print to console: `print(f"⚠️  Phase 1: {char_id} fallback to idle ({error})")`

**Note**: "idle" is a technical marker. Phase 2a arbiter should handle it
as "character does nothing this tick". This will be addressed in B.3a
when designing Phase 2a prompts.

---

## Algorithm

```
1. Create PromptRenderer with simulation path
2. Group characters by location (for "others" context)
3. For each character:
   a. Get character's location
   b. Get others in same location (identity only)
   c. Render system prompt (no variables in default)
   d. Render user prompt with context
   e. Create LLMRequest with entity_key="intention:{id}"
4. Execute batch via llm_client.create_batch()
5. Process results:
   - Success → use IntentionResponse
   - LLMError → fallback + warning + console message
6. Return PhaseResult(success=True, data=intentions)
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
└── phase1.py          # IntentionResponse, execute()
```

---

## Usage Examples

### Basic Execution

```python
from src.config import Config
from src.utils.storage import load_simulation
from src.utils.llm import LLMClient
from src.utils.llm_adapters.openai import OpenAIAdapter
from src.phases.phase1 import execute

config = Config.load()
simulation = load_simulation(Path("simulations/demo-sim"))

adapter = OpenAIAdapter(config.phase1)
characters_list = list(simulation.characters.values())
llm_client = LLMClient(
    adapter=adapter,
    entities=[c.model_dump() for c in characters_list],
    default_depth=config.phase1.response_chain_depth,
)

result = await execute(simulation, config, llm_client)

# result.data = {
#     "ogilvy": IntentionResponse(intention="Approach the cylinder..."),
#     "henderson": IntentionResponse(intention="Take notes..."),
# }
```

### Accessing Intentions

```python
result = await execute(simulation, config, llm_client)

for char_id, intention in result.data.items():
    print(f"{char_id}: {intention.intention}")
```

---

## Error Handling

### Exit Codes

Phase 1 does not exit directly. Returns PhaseResult, Runner handles exit codes.

### Failure Modes

| Situation | Handling |
|-----------|----------|
| LLM timeout (after retries) | Fallback to idle |
| LLM rate limit (after retries) | Fallback to idle |
| LLM refusal | Fallback to idle |
| LLM incomplete response | Fallback to idle |
| Prompt template not found | Exception propagates to Runner |
| Prompt render error | Exception propagates to Runner |

### Partial Failure

If some characters succeed and some fail:
- Successful characters get real intentions
- Failed characters get idle fallback
- Phase returns success=True (simulation continues)

---

## Test Coverage

### Unit Tests (tests/unit/test_phase1.py)

**Context Assembly:**
- test_build_context_single_character — alone in location
- test_build_context_multiple_characters — others list populated
- test_build_context_empty_memory — handles empty memory cells

**Prompt Rendering:**
- test_render_system_prompt — renders without variables
- test_render_user_prompt — renders with full context
- test_render_uses_simulation_override — picks sim prompt over default

**Batch Execution:**
- test_execute_all_success — all characters get intentions
- test_execute_partial_failure — mix of success and fallback
- test_execute_all_failure — all fallback to idle

**Fallback:**
- test_fallback_logs_warning — logger.warning called
- test_fallback_prints_console — print called with message
- test_fallback_returns_idle — intention is "idle"

**Result Structure:**
- test_result_has_all_characters — every character in output
- test_result_success_always_true — success=True even with fallbacks

### Integration Tests (tests/integration/test_phase1_integration.py)

**With Real LLM:**
- test_generate_intention_real_llm — actual intention generated
- test_intention_respects_character_context — intention reflects character
- test_intention_language_matches_simulation — Russian sim → Russian intention

Markers: `@pytest.mark.integration`, `@pytest.mark.slow`

Skip condition: `OPENAI_API_KEY` not set

---

## Implementation Notes

### Logging

- DEBUG: context assembly, prompt rendering
- WARNING: fallback to idle (with error details)

### Console Output

Fallback message format:
```
⚠️  Phase 1: {character_id} fallback to idle ({error_type}: {message})
```

Example:
```
⚠️  Phase 1: ogilvy fallback to idle (LLMRateLimitError: Rate limit after 3 attempts)
```

### Character Grouping

Characters grouped by `character.state.location` to build "others" list efficiently.
O(n) grouping, then O(1) lookup per character.

### Entity Conversion

LLMClient expects `list[dict]`, not Pydantic models. Convert via `model_dump()`:

```python
entities = [char.model_dump() for char in simulation.characters.values()]
```
