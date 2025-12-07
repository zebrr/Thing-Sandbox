# phase_4.md

## Status: READY

Phase 4 updates character memories after tick events. Implements FIFO queue
with K cells: when queue is full, oldest cell is summarized into compressed
history before adding new memory. Uses LLM for summarization with graceful
fallback on errors.

---

## Public API

### SummaryResponse

Pydantic model for LLM structured output.

```python
class SummaryResponse(BaseModel):
    summary: str = Field(..., min_length=1)
```

Corresponds to `src/schemas/SummaryResponse.schema.json`.

### execute(simulation, config, llm_client, pending_memories) -> PhaseResult

Main entry point for Phase 4.

- **Input**:
  - simulation (Simulation) — current simulation state with characters
  - config (Config) — application configuration (includes memory_cells)
  - llm_client (LLMClient) — client for LLM requests
  - pending_memories (dict[str, str]) — mapping character_id → memory_entry from Phase 3
- **Returns**: PhaseResult with:
  - success: True (always, due to fallback strategy)
  - data: None (memory updates applied in-place to simulation)
- **Side effects**:
  - Mutates character.memory in simulation (summary, cells)
  - Logs warning for each fallback
  - Accumulates usage in character entities via llm_client

---

## Data Flow

### Input

- **simulation.characters**: dict[str, Character] — all characters
- **config.simulation.memory_cells**: int — K, maximum cells before summarization
- **llm_client**: LLMClient — configured for Phase 4
- **pending_memories**: dict[str, str] — memory entries from Phase 3

### Context Assembly (per character needing summarization)

| Template Variable | Source | Notes |
|-------------------|--------|-------|
| character | Character | identity, memory (for old summary and dropping cell) |
| simulation | Simulation | current_tick for context |

### Output

- PhaseResult with data=None
- Memory updates applied directly to simulation.characters

### Memory Structure

```json
"memory": {
  "cells": [
    {"tick": 5, "text": "..."},   // [0] - newest
    {"tick": 4, "text": "..."},
    {"tick": 3, "text": "..."}    // [-1] - oldest, drops when K reached
  ],
  "summary": "Compressed history before tick 3..."
}
```

---

## LLM Integration

### Prompts

- **System**: `phase4_summary_system.md`
- **User**: `phase4_summary_user.md`

Resolution: simulation override → default (via PromptRenderer).

### Schema

`SummaryResponse` — single field `summary: str`.

### Batch Execution

Only characters needing summarization (len(cells) >= K) are batched.
Characters with space in queue skip LLM call entirely.

### Entity Key Format

`"memory:{character_id}"` — for response chain management.

---

## Fallback Strategy

**Strategy: Memory Unchanged (Variant A)**

When LLM fails for a character (all retries exhausted):

1. Do NOT update character's memory at all
2. Log warning with error details
3. Character "forgets" this tick's events (safe data preservation)

**Rationale**: Preserves existing memory integrity. The character misses
one tick of memory rather than losing compressed historical data.

**Consequences**:
- pending_memory for this character is discarded
- No cells shift, no summary update
- Next tick will retry normally

---

## Algorithm

```
Input:
  - pending_memories: {char_id: memory_entry} from Phase 3
  - K = config.simulation.memory_cells

1. Create PromptRenderer with simulation path

2. Partition characters into two groups:
   - needs_summary: len(cells) >= K (must summarize before adding)
   - has_space: len(cells) < K (can add directly)

3. For characters in needs_summary:
   a. Build context: character (with memory), simulation (for tick)
   b. Render system and user prompts
   c. Create LLMRequest with entity_key="memory:{char_id}"

4. Execute batch via llm_client.create_batch()

5. Process summarization results:
   For each (char, result) in zip(needs_summary_chars, results):
     IF isinstance(result, LLMError):
       - Log WARNING: "Phase 4: {char_id} fallback - memory unchanged ({error_type}: {error})"
       - Skip this character (no memory update)
     ELSE:
       - Update character.memory.summary = result.summary
       - Remove oldest cell: character.memory.cells.pop()
       - Insert new cell at front: cells.insert(0, {tick, pending_memory})

6. Process characters with space (no LLM needed):
   For each char in has_space:
     - Insert new cell at front: cells.insert(0, {tick, pending_memory})

7. Return PhaseResult(success=True, data=None)
```

### Edge Cases

| Case | Handling |
|------|----------|
| Character not in pending_memories | Skip (no memory to add) |
| Character not in simulation.characters | Log warning, skip |
| Empty pending_memory string | Still add as cell (valid "nothing happened") |
| cells is empty, summary is empty | Normal case for new character, just add cell |

---

## Dependencies

- **Standard Library**: logging
- **External**: pydantic>=2.0
- **Internal**:
  - src.config.Config
  - src.utils.storage.Simulation, Character
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
├── phase1.py
├── phase2a.py
├── phase2b.py
├── phase3.py
└── phase4.py          # SummaryResponse, execute()
```

---

## Usage Examples

### Basic Execution

```python
from src.config import Config
from src.utils.storage import load_simulation
from src.utils.llm import LLMClient
from src.utils.llm_adapters.openai import OpenAIAdapter
from src.phases.phase4 import execute

config = Config.load()
simulation = load_simulation(Path("simulations/demo-sim"))

# pending_memories from Phase 3
pending_memories = {
    "ogilvy": "I approached the cylinder and heard strange sounds...",
    "henderson": "I watched Ogilvy from a distance, taking notes...",
}

adapter = OpenAIAdapter(config.phase4)
characters_list = list(simulation.characters.values())
llm_client = LLMClient(
    adapter=adapter,
    entities=[c.model_dump() for c in characters_list],
    default_depth=config.phase4.response_chain_depth,
)

result = await execute(simulation, config, llm_client, pending_memories)

# Memory updated in-place
print(simulation.characters["ogilvy"].memory.cells[0].text)
# "I approached the cylinder and heard strange sounds..."
```

### Checking Memory State

```python
char = simulation.characters["ogilvy"]
print(f"Summary: {char.memory.summary}")
print(f"Cells: {len(char.memory.cells)}")
for cell in char.memory.cells:
    print(f"  Tick {cell.tick}: {cell.text[:50]}...")
```

---

## Error Handling

### Exit Codes

Phase 4 does not exit directly. Returns PhaseResult, Runner handles exit codes.

### Failure Modes

| Situation | Handling |
|-----------|----------|
| LLM timeout (after retries) | Fallback: memory unchanged |
| LLM rate limit (after retries) | Fallback: memory unchanged |
| LLM refusal | Fallback: memory unchanged |
| LLM incomplete response | Fallback: memory unchanged |
| Character not in simulation | Log warning, skip |
| Character not in pending_memories | Skip (nothing to add) |
| Prompt template not found | Exception propagates to Runner |
| Prompt render error | Exception propagates to Runner |

### Partial Failure

If some characters succeed and some fail:
- Successful characters get updated memory
- Failed characters keep old memory (this tick's events lost)
- Phase returns success=True (simulation continues)

---

## Test Coverage

### Unit Tests (tests/unit/test_phase4.py)

**SummaryResponse:**
- test_summary_response_creation — basic creation
- test_summary_response_unicode — Cyrillic support
- test_summary_response_empty_rejected — min_length=1 validation

**Partitioning:**
- test_partition_mixed — some need summarization, some have space
- test_partition_empty_cells — new character with empty cells array

**Memory Operations:**
- test_add_cell_at_front — new cell becomes cells[0]
- test_add_cell_preserves_order — existing cells shift right

**Batch Execution:**
- test_execute_all_need_summary — all go through LLM, memory updated
- test_execute_none_need_summary — no LLM calls, direct insert
- test_execute_mixed — correct handling of both groups

**Fallback:**
- test_execute_llm_error_fallback — memory unchanged on error
- test_fallback_preserves_existing_memory — cells and summary unchanged, logs warning

**Edge Cases:**
- test_execute_empty_pending_memories — no updates, no errors

### Integration Tests (tests/integration/test_phase4_integration.py)

Uses custom test fixtures with prepared memory state.

**With Real LLM:**
- test_summarize_memory_real_llm — full summarization flow, summary updated, FIFO shift correct
- test_no_llm_call_when_space_available — no LLM call when cells < K
- test_usage_tracked_after_summarization — token usage statistics recorded

Markers: `@pytest.mark.integration`, `@pytest.mark.slow`

Skip condition: `OPENAI_API_KEY` not set

---

## Implementation Notes

### Logging

- DEBUG: context assembly, prompt rendering, cell operations
- WARNING: fallback (with error details)

Log format (via Architecture conventions):
```
2025.06.05 14:32:18 | INFO    | 🧠 phase4: Complete (2 chars, 3,100 tokens, 800 reasoning)
2025.06.05 14:32:17 | WARNING | 🧠 phase4: henderson fallback - memory unchanged (LLMTimeoutError: Timeout after 3 attempts)
```

### Memory Cell Structure

Each cell is a `MemoryCell` Pydantic model with `tick` and `text`:

```python
from src.utils.storage import MemoryCell

new_cell = MemoryCell(
    tick=simulation.current_tick,
    text=pending_memories[char_id],
)
character.memory.cells.insert(0, new_cell)
```

### Entity Conversion

LLMClient expects `list[dict]`, not Pydantic models. Convert via `model_dump()`:

```python
entities = [char.model_dump() for char in simulation.characters.values()]
```

### Mutation Strategy

Phase 4 mutates simulation.characters in-place. This is consistent with
Phase 3 and allows Runner to save all changes atomically at tick end.

### K Configuration

Memory cell count K is read from `config.simulation.memory_cells`.
Default is 5 (set in config.toml).
