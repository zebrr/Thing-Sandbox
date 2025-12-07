# TS-B.4b-PHASE4-001: Implement Phase 4 (Memory Summarization)

## References

Read before starting:
- `docs/specs/phase_4.md` — specification for this phase
- `docs/specs/util_llm.md` — LLMClient API
- `docs/specs/util_prompts.md` — PromptRenderer API
- `docs/specs/util_storage.md` — Simulation, Character models (especially memory structure)
- `docs/specs/core_config.md` — SimulationConfig.memory_cells
- `docs/Thing' Sandbox LLM Approach v2.md` — section 10 (Graceful Degradation)
- `docs/Thing' Sandbox LLM Usage Tracking.md` — logging format
- `src/schemas/SummaryResponse.schema.json` — output schema
- `src/prompts/phase4_summary_*.md` — prompt templates

## Context

Phase 4 is currently a stub (no-op). We need to implement FIFO memory with LLM summarization.

**Current state:**
- Stub exists at `src/phases/phase4.py` — returns `PhaseResult(success=True, data=None)`
- Prompts ready: `src/prompts/phase4_summary_system.md`, `src/prompts/phase4_summary_user.md`
- Runner already passes `pending_memories` from Phase 3
- Infrastructure ready: LLMClient, PromptRenderer, Storage

**Goal:**
- Implement FIFO memory queue with K cells (from `config.simulation.memory_cells`)
- When queue full: summarize oldest cell into compressed history via LLM
- Fallback strategy: on LLM error, leave memory unchanged (character "forgets" this tick)

## Algorithm Summary

```
For each character with pending_memory:
  1. If len(cells) >= K:
     - Call LLM: old_summary + oldest_cell → new_summary
     - On success: update summary, remove oldest cell, add new cell at front
     - On error: skip this character entirely (fallback)
  2. If len(cells) < K:
     - Just add new cell at front (no LLM needed)
```

## Steps

### 1. Define SummaryResponse model

In `src/phases/phase4.py`, add Pydantic model:

```python
from pydantic import BaseModel, Field

class SummaryResponse(BaseModel):
    """LLM structured output for memory summarization."""
    summary: str = Field(..., min_length=1)
```

### 2. Implement character partitioning

Separate characters into those needing summarization and those with space:

```python
def _partition_characters(
    characters: dict[str, Character],
    pending_memories: dict[str, str],
    max_cells: int,
) -> tuple[list[Character], list[Character]]:
    """Partition characters by whether they need summarization.
    
    Returns:
        (needs_summary, has_space) — two lists of characters
    """
    needs_summary: list[Character] = []
    has_space: list[Character] = []
    
    for char_id, char in characters.items():
        if char_id not in pending_memories:
            continue  # No memory to add for this character
        
        if len(char.memory.cells) >= max_cells:
            needs_summary.append(char)
        else:
            has_space.append(char)
    
    return needs_summary, has_space
```

### 3. Implement memory cell operations

Helper to add new memory cell:

```python
def _add_memory_cell(character: Character, tick: int, text: str) -> None:
    """Insert new memory cell at front of queue."""
    new_cell = MemoryCell(tick=tick, text=text)
    character.memory.cells.insert(0, new_cell)
```

Note: Check if `MemoryCell` is available from storage module, or use dict:
```python
new_cell = {"tick": tick, "text": text}
```

### 4. Implement batch execution for summarization

Build requests only for characters needing summary:

```python
requests: list[LLMRequest] = []

for char in needs_summary:
    system_prompt = renderer.render("phase4_summary_system", {})
    user_prompt = renderer.render("phase4_summary_user", {
        "character": char,
        "simulation": simulation,
    })
    
    requests.append(LLMRequest(
        instructions=system_prompt,
        input_data=user_prompt,
        schema=SummaryResponse,
        entity_key=f"memory:{char.identity.id}",
    ))

if requests:
    results = await llm_client.create_batch(requests)
```

### 5. Process summarization results with fallback

```python
for char, result in zip(needs_summary, results):
    char_id = char.identity.id
    
    if isinstance(result, LLMError):
        error_type = type(result).__name__
        logger.warning(
            "Phase 4: %s fallback - memory unchanged (%s: %s)",
            char_id, error_type, result
        )
        continue  # Skip this character entirely
    
    # Success: update memory
    char.memory.summary = result.summary
    char.memory.cells.pop()  # Remove oldest
    _add_memory_cell(char, simulation.current_tick, pending_memories[char_id])
```

### 6. Process characters with space (no LLM)

```python
for char in has_space:
    char_id = char.identity.id
    _add_memory_cell(char, simulation.current_tick, pending_memories[char_id])
```

### 7. Update execute() function

Replace stub with full implementation:

```python
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
    pending_memories: dict[str, str],
) -> PhaseResult:
    """Update character memories with FIFO queue and summarization."""
    
    # Get K from config
    max_cells = config.simulation.memory_cells
    
    # Create renderer
    sim_path = config.project_root / "simulations" / simulation.id
    renderer = PromptRenderer(config, sim_path=sim_path)
    
    # Partition characters
    needs_summary, has_space = _partition_characters(
        simulation.characters, pending_memories, max_cells
    )
    
    # ... batch execution and processing ...
    
    return PhaseResult(success=True, data=None)
```

### 8. Add imports

```python
import logging

from pydantic import BaseModel, Field

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient, LLMRequest
from src.utils.llm_errors import LLMError
from src.utils.prompts import PromptRenderer
from src.utils.storage import Character, Simulation

logger = logging.getLogger(__name__)
```

## Testing

### Run quality checks first

```bash
cd /path/to/thing-sandbox
source venv/bin/activate

ruff check src/phases/phase4.py
ruff format src/phases/phase4.py
mypy src/phases/phase4.py
```

### Unit tests

Create `tests/unit/test_phase4.py`:

```bash
pytest tests/unit/test_phase4.py -v
```

Test cases (mock LLMClient):

**SummaryResponse:**
- `test_summary_response_creation` — basic creation works
- `test_summary_response_unicode` — Cyrillic characters work
- `test_summary_response_empty_rejected` — empty string fails validation

**Partitioning:**
- `test_partition_all_need_summary` — all chars at max cells
- `test_partition_none_need_summary` — all chars have space
- `test_partition_mixed` — some need, some don't
- `test_partition_empty_cells` — new character with no cells
- `test_partition_char_not_in_pending` — character skipped if no pending memory

**Memory Operations:**
- `test_add_cell_at_front` — new cell at index 0
- `test_add_cell_preserves_order` — existing cells shift right
- `test_cells_pop_removes_oldest` — pop() removes last element

**Batch Execution:**
- `test_execute_all_need_summary` — correct number of LLM requests
- `test_execute_none_need_summary` — no LLM calls made
- `test_execute_mixed` — both groups handled correctly
- `test_execute_creates_correct_entity_keys` — format "memory:{char_id}"

**Fallback:**
- `test_execute_llm_error_fallback` — memory unchanged on error
- `test_execute_partial_failure` — mix success/failure
- `test_fallback_logs_warning` — logger.warning called with details
- `test_fallback_preserves_existing_memory` — cells and summary intact

**Edge Cases:**
- `test_execute_empty_pending_memories` — no updates, no errors
- `test_execute_character_not_in_pending` — character skipped
- `test_execute_empty_memory_string` — empty string still added as cell

**Result:**
- `test_result_success_always_true` — success=True even with fallbacks
- `test_result_data_is_none` — data=None (updates in-place)

### Integration tests

Create `tests/integration/test_phase4_integration.py`:

```bash
pytest tests/integration/test_phase4_integration.py -v -m integration
```

**Important**: Phase 4 only calls LLM when `len(cells) >= K`. Tests must prepare
simulation with full memory to trigger summarization.

**Test fixture helper:**

```python
def make_test_simulation_with_full_memory(config: Config) -> Simulation:
    """Create simulation where characters have K cells (triggers summarization)."""
    K = config.simulation.memory_cells  # 5
    
    # Build cells array with K entries
    cells = [
        MemoryCell(tick=i, text=f"Memory from tick {i}")
        for i in range(K - 1, -1, -1)  # [4,3,2,1,0] order (newest first)
    ]
    
    return Simulation(
        id="test-phase4-sim",
        current_tick=K,  # Next tick after filling memory
        ...
        characters={
            "test_char": Character(
                ...
                memory=CharacterMemory(
                    cells=cells,
                    summary="Previous events summary.",
                ),
            ),
        },
        ...
    )
```

**Test cases (real LLM, skip if no API key):**

1. `test_summarize_memory_real_llm` — основной тест суммаризации:
   - Setup: персонаж с `len(cells) == K`, непустой summary
   - Execute: Phase 4 с pending_memory
   - Assert:
     - `result.success is True`
     - `character.memory.summary` изменился (не равен старому)
     - `len(character.memory.cells) == K` (остался тот же размер)
     - `character.memory.cells[0].text == pending_memory` (новая ячейка спереди)
     - `character.memory.cells[0].tick == simulation.current_tick`

2. `test_summary_language_matches_content` — язык суммаризации:
   - Setup: cells и summary на русском с кириллицей
   - Execute: Phase 4
   - Assert: новый summary содержит кириллицу (`any('\u0400' <= c <= '\u04ff' for c in summary)`)

3. `test_summary_incorporates_dropped_cell` — качество суммаризации:
   - Setup: oldest cell (cells[-1]) содержит уникальный маркер, например "встретил Марсианина"
   - Execute: Phase 4
   - Assert: новый summary содержит упоминание "Марсианин" или семантически связанное
   - Note: этот тест может быть flaky, можно сделать soft assertion или skip

4. `test_no_llm_call_when_space_available` — оптимизация (нет LLM если есть место):
   - Setup: персонаж с `len(cells) < K` (например, 2 ячейки)
   - Execute: Phase 4 с pending_memory
   - Assert:
     - `llm_client.get_last_batch_stats().request_count == 0`
     - `len(character.memory.cells) == 3` (было 2, стало 3)
     - `character.memory.cells[0].text == pending_memory`

5. `test_usage_tracked_after_summarization` — статистика:
   - Setup: персонаж с полной памятью
   - Execute: Phase 4
   - Assert: `llm_client.get_last_batch_stats().total_tokens > 0`

Use `@pytest.mark.integration` and `@pytest.mark.slow` markers.
Skip if `OPENAI_API_KEY` not set.
Use `@pytest.mark.timeout(180)` for each test.

### Manual test with demo-sim

```bash
# Reset demo-sim
python -m src.cli reset demo-sim

# Run 6+ ticks to trigger summarization (K=5)
for i in {1..6}; do
    echo "=== Tick $i ==="
    python -m src.cli run demo-sim
done

# Check memory in character files
cat simulations/demo-sim/characters/ogilvy.json | jq '.memory'
```

Expected: after 5 ticks, summary should contain compressed history.

## Deliverables

1. **Updated module:** `src/phases/phase4.py`
   - SummaryResponse model
   - _partition_characters() helper
   - _add_memory_cell() helper
   - Full execute() implementation
   - Fallback handling with warning logs

2. **Unit tests:** `tests/unit/test_phase4.py`
   - All test cases from spec

3. **Integration tests:** `tests/integration/test_phase4_integration.py`
   - Real LLM tests with skip condition

4. **Updated spec:** `docs/specs/phase_4.md`
   - Change status from DRAFT to READY

5. **Report:** `docs/tasks/TS-B.4b-PHASE4-001_REPORT.md`

## Notes

- Memory structure: `cells` is list with [0]=newest, [-1]=oldest. Use `insert(0, ...)` and `pop()`.
- MemoryCell may be a Pydantic model or dict — check storage module. User prompt template expects `character.memory.cells[-1].text`.
- Prompt template uses `character.memory.summary | default("Nothing yet...")` — works with empty string.
- Current tick for new cell comes from `simulation.current_tick` (before increment by runner).
- Runner increments tick AFTER Phase 4, so use current_tick as-is.
