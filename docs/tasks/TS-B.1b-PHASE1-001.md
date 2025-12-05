# TS-B.1b-PHASE1-001: Implement Phase 1 (Character Intentions)

## References

Read before starting:
- `docs/specs/phase_1.md` — specification for this phase
- `docs/specs/util_llm.md` — LLMClient API
- `docs/specs/util_prompts.md` — PromptRenderer API
- `docs/specs/util_storage.md` — Simulation, Character, Location models
- `docs/Thing' Sandbox LLM Prompting.md` — section 5 (Phase 1 prompting)
- `src/schemas/IntentionResponse.schema.json` — output schema

## Context

Phase 1 is currently a stub returning `{"intention": "idle"}` for all characters.
We need to implement real LLM-based intention generation.

**Current state:**
- Stub exists at `src/phases/phase1.py`
- Prompts ready: `src/prompts/phase1_intention_*.md` and `simulations/_templates/demo-sim/prompts/`
- Infrastructure ready: LLMClient, PromptRenderer, Storage

**Goal:**
- Replace stub with real implementation
- Each character gets context (identity, state, memory, location, others)
- LLM generates intention via batch execution
- Fallback to "idle" on LLM errors with warning + console message

## Steps

### 1. Define IntentionResponse model

In `src/phases/phase1.py`, add Pydantic model:

```python
from pydantic import BaseModel

class IntentionResponse(BaseModel):
    intention: str
```

### 2. Implement context assembly

Create helper to group characters by location:

```python
def _group_by_location(characters: dict[str, Character]) -> dict[str, list[Character]]:
    """Group characters by their current location."""
    groups: dict[str, list[Character]] = {}
    for char in characters.values():
        loc_id = char.state.location
        if loc_id not in groups:
            groups[loc_id] = []
        groups[loc_id].append(char)
    return groups
```

### 3. Implement prompt rendering

For each character:
- Get location from `simulation.locations[char.state.location]`
- Get others (same location, exclude self, identity only)
- Render system prompt (empty context for default template)
- Render user prompt with `{character, location, others}`

### 4. Implement batch execution

Build `LLMRequest` list and call `llm_client.create_batch()`:

```python
requests = []
for char in simulation.characters.values():
    system = renderer.render("phase1_intention_system", {})
    user = renderer.render("phase1_intention_user", {
        "character": char,
        "location": location,
        "others": others,
    })
    requests.append(LLMRequest(
        instructions=system,
        input_data=user,
        schema=IntentionResponse,
        entity_key=f"intention:{char.identity.id}",
    ))

results = await llm_client.create_batch(requests)
```

### 5. Implement fallback handling

Process results with fallback for errors:

```python
intentions: dict[str, IntentionResponse] = {}

for char, result in zip(characters, results):
    char_id = char.identity.id
    if isinstance(result, LLMError):
        logger.warning(f"Phase 1: {char_id} fallback to idle ({result})")
        print(f"⚠️  Phase 1: {char_id} fallback to idle ({result})")
        intentions[char_id] = IntentionResponse(intention="idle")
    else:
        intentions[char_id] = result

return PhaseResult(success=True, data=intentions)
```

### 6. Update execute() signature

Keep existing signature, replace stub implementation:

```python
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
) -> PhaseResult:
```

### 7. Add imports

```python
import logging
from pathlib import Path

from pydantic import BaseModel

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient, LLMRequest
from src.utils.llm_errors import LLMError
from src.utils.prompts import PromptRenderer
from src.utils.storage import Simulation, Character, Location

logger = logging.getLogger(__name__)
```

## Testing

### Run quality checks first

```bash
cd /path/to/thing-sandbox
source venv/bin/activate

ruff check src/phases/phase1.py
ruff format src/phases/phase1.py
mypy src/phases/phase1.py
```

### Unit tests

Create `tests/unit/test_phase1.py`:

```bash
pytest tests/unit/test_phase1.py -v
```

Test cases (mock LLMClient):
- `test_build_context_single_character` — alone in location, others=[]
- `test_build_context_multiple_characters` — others list correct
- `test_execute_all_success` — all characters get intentions
- `test_execute_partial_failure` — some success, some fallback
- `test_execute_all_failure` — all fallback to idle
- `test_fallback_logs_warning` — logger.warning called
- `test_fallback_prints_console` — print called (use capsys)
- `test_result_has_all_characters` — every character in output
- `test_result_success_always_true` — success=True even with fallbacks

### Integration test

Create `tests/integration/test_phase1_integration.py`:

```bash
pytest tests/integration/test_phase1_integration.py -v -m integration
```

Test cases (real LLM, skip if no API key):
- `test_generate_intention_real_llm` — actual intention generated
- `test_intention_reflects_character` — intention relates to character context

Use `@pytest.mark.integration` and `@pytest.mark.slow` markers.
Skip if `OPENAI_API_KEY` not set.

### Manual test with demo-sim

```bash
# Reset demo-sim to clean state
python -m src.cli reset demo-sim

# Run one tick (will use real Phase 1, stub phases 2-4)
python -m src.cli run demo-sim

# Check output — should see real intentions in console
```

## Deliverables

1. **Updated module:** `src/phases/phase1.py`
   - IntentionResponse model
   - Real execute() implementation
   - Fallback handling with console output

2. **Unit tests:** `tests/unit/test_phase1.py`
   - All test cases from spec

3. **Integration tests:** `tests/integration/test_phase1_integration.py`
   - Real LLM tests with skip condition

4. **Updated spec:** `docs/specs/phase_1.md`
   - Change status to READY

5. **Report:** `docs/tasks/TS-B.1b-PHASE1-001_REPORT.md`

## Notes

- PromptRenderer needs simulation path for override resolution. Get it from config or pass explicitly.
- Characters are Pydantic models. PromptRenderer works with them directly (Jinja2 uses getattr).
- LLMClient expects `list[dict]` for entities — convert via `model_dump()`.
- Keep character order consistent between request building and result processing.
