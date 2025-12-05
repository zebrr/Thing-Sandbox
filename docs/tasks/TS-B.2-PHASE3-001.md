# TS-B.2-PHASE3-001: Implement Phase 3 (Apply Results)

## References

Read before starting:
- `docs/specs/phase_3.md` — specification for this task
- `docs/specs/phase_1.md` — reference for phase implementation patterns
- `docs/specs/core_runner.md` — runner integration context
- `src/phases/phase1.py` — reference implementation
- `src/phases/phase2a.py` — current stub, add Pydantic models here
- `src/phases/phase4.py` — update signature
- `src/runner.py` — update phase calls
- `src/schemas/Master.schema.json` — JSON schema for MasterOutput

## Context

Phase 3 applies arbitration results to simulation state. It's pure mechanics — no LLM calls.

**Current state:**
- `phase3.py` is a stub returning `PhaseResult(success=True, data=None)`
- `phase2a.py` returns `dict[str, Any]` without Pydantic models
- `runner.py` passes `None` to phases 3 and 4 with `# type: ignore`
- `phase4.py` doesn't accept `pending_memories` parameter

**Goal:**
- Implement Phase 3 that applies MasterOutput to simulation
- Add Pydantic models to phase2a.py for type safety
- Update runner.py to pass data between phases
- Update phase4.py signature to accept pending_memories

## Steps

### 1. Add Pydantic models to `src/phases/phase2a.py`

Add these models (keep existing code, add models before `execute` function):

```python
class CharacterUpdate(BaseModel):
    """Update for a single character from arbiter.
    
    Example:
        >>> update = CharacterUpdate(
        ...     location="forest",
        ...     internal_state="Tired",
        ...     external_intent="Rest",
        ...     memory_entry="I walked to the forest..."
        ... )
    """
    location: str
    internal_state: str
    external_intent: str
    memory_entry: str


class LocationUpdate(BaseModel):
    """Update for location state from arbiter.
    
    Example:
        >>> update = LocationUpdate(moment="Evening falls")
    """
    moment: str | None = None
    description: str | None = None


class MasterOutput(BaseModel):
    """Complete arbiter output for one location.
    
    Corresponds to src/schemas/Master.schema.json.
    
    Example:
        >>> output = MasterOutput(
        ...     tick=5,
        ...     location_id="tavern",
        ...     characters={"bob": CharacterUpdate(...)},
        ...     location=LocationUpdate()
        ... )
    """
    tick: int
    location_id: str
    characters: dict[str, CharacterUpdate]
    location: LocationUpdate
```

Update the stub's `execute` function to use `MasterOutput` type hint and return proper structure:

```python
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
) -> PhaseResult:
    """..."""
    results: dict[str, MasterOutput] = {}
    
    for loc_id, location in simulation.locations.items():
        # ... existing logic ...
        
        results[loc_id] = MasterOutput(
            tick=simulation.current_tick,
            location_id=loc_id,
            characters={
                char_id: CharacterUpdate(
                    location=char.state.location,
                    internal_state=char.state.internal_state or "",
                    external_intent=char.state.external_intent or "",
                    memory_entry="[Stub] Nothing notable happened.",
                )
                for char_id, char in chars_here.items()
            },
            location=LocationUpdate(moment=None, description=None),
        )
    
    return PhaseResult(success=True, data=results)
```

### 2. Implement `src/phases/phase3.py`

Replace stub with full implementation per `docs/specs/phase_3.md`:

```python
"""Phase 3: Apply arbitration results.

Applies MasterOutput to simulation state: updates character locations,
internal states, external intents, and collects memory entries for Phase 4.
Pure mechanics, no LLM calls.

Example:
    >>> from src.phases.phase3 import execute
    >>> result = await execute(simulation, config, master_results)
    >>> result.data["pending_memories"]["ogilvy"]
    'I approached the cylinder...'
"""

import logging

from src.config import Config
from src.phases.common import PhaseResult
from src.phases.phase2a import MasterOutput
from src.utils.storage import Simulation

logger = logging.getLogger(__name__)


async def execute(
    simulation: Simulation,
    config: Config,
    master_results: dict[str, MasterOutput],
) -> PhaseResult:
    """Apply arbiter results to simulation state.
    
    Updates characters (location, internal_state, external_intent) and
    locations (moment, description). Collects memory_entry for each
    character into pending_memories for Phase 4.
    
    Args:
        simulation: Current simulation state (mutated in place).
        config: Application configuration (unused, for signature consistency).
        master_results: Mapping location_id → MasterOutput from Phase 2a.
    
    Returns:
        PhaseResult with success=True and data containing:
        {"pending_memories": {char_id: memory_entry, ...}}
    
    Example:
        >>> result = await execute(sim, config, master_results)
        >>> result.data["pending_memories"]["bob"]
        'I tried to open the door...'
    """
    pending_memories: dict[str, str] = {}
    
    for location_id, master_output in master_results.items():
        # Validate location exists
        if location_id not in simulation.locations:
            logger.warning(
                "Phase 3: unknown location '%s' in master_results, skipping",
                location_id,
            )
            print(f"⚠️  Phase 3: unknown location '{location_id}' in master_results, skipping")
            continue
        
        location = simulation.locations[location_id]
        
        # Apply location updates
        if master_output.location.moment is not None:
            location.state.moment = master_output.location.moment
            logger.debug("Phase 3: updated moment for location '%s'", location_id)
        
        if master_output.location.description is not None:
            location.identity.description = master_output.location.description
            logger.debug("Phase 3: updated description for location '%s'", location_id)
        
        # Apply character updates
        for char_id, char_update in master_output.characters.items():
            # Validate character exists
            if char_id not in simulation.characters:
                logger.warning(
                    "Phase 3: unknown character '%s' in location '%s', skipping",
                    char_id,
                    location_id,
                )
                print(
                    f"⚠️  Phase 3: unknown character '{char_id}' "
                    f"in location '{location_id}', skipping"
                )
                continue
            
            character = simulation.characters[char_id]
            
            # Validate target location
            if char_update.location not in simulation.locations:
                logger.warning(
                    "Phase 3: invalid target location '%s' for character '%s', keeping current",
                    char_update.location,
                    char_id,
                )
                print(
                    f"⚠️  Phase 3: invalid target location '{char_update.location}' "
                    f"for character '{char_id}', keeping current"
                )
                # Keep current location, still update other fields
            else:
                character.state.location = char_update.location
            
            # Update state fields
            character.state.internal_state = char_update.internal_state
            character.state.external_intent = char_update.external_intent
            
            # Collect memory entry
            pending_memories[char_id] = char_update.memory_entry
            
            logger.debug("Phase 3: updated character '%s'", char_id)
    
    return PhaseResult(success=True, data={"pending_memories": pending_memories})
```

### 3. Update `src/phases/phase4.py` signature

Add `pending_memories` parameter to the stub:

```python
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
    pending_memories: dict[str, str],  # char_id → memory_entry
) -> PhaseResult:
    """Update character memories (stub: no-op).

    In real implementation will:
    - FIFO shift memory cells
    - Summarize evicted cell into summary (LLM call)
    - Add new memory_entry from pending_memories to cell 0

    Args:
        simulation: Current simulation state.
        config: Application configuration.
        llm_client: LLM client for summarization calls (unused in stub).
        pending_memories: Mapping char_id → memory_entry from Phase 3.

    Returns:
        PhaseResult with data=None.

    Example:
        >>> result = await execute(sim, config, client, {"bob": "I saw..."})
        >>> result.success
        True
    """
    # Real implementation will use pending_memories
    _ = pending_memories  # Silence unused warning
    
    return PhaseResult(success=True, data=None)
```

### 4. Update `src/phases/__init__.py`

Export new models:

```python
from src.phases.phase2a import (
    CharacterUpdate,
    LocationUpdate,
    MasterOutput,
    execute as execute_phase2a,
)
```

### 5. Update `src/runner.py`

Update `_execute_phases` method to pass data between phases:

```python
async def _execute_phases(self, simulation: Simulation, llm_client: LLMClient) -> None:
    """Execute all phases sequentially."""
    # Phase 1: Intentions
    result1 = await execute_phase1(simulation, self._config, llm_client)
    if not result1.success:
        raise PhaseError("phase1", result1.error or "Unknown error")
    logger.debug("Phase 1 completed: %d intentions", len(result1.data))

    # Phase 2a: Scene resolution
    result2a = await execute_phase2a(simulation, self._config, llm_client)
    if not result2a.success:
        raise PhaseError("phase2a", result2a.error or "Unknown error")
    logger.debug("Phase 2a completed: %d locations", len(result2a.data))

    # Phase 2b: Narrative generation
    result2b = await execute_phase2b(simulation, self._config, llm_client)
    if not result2b.success:
        raise PhaseError("phase2b", result2b.error or "Unknown error")
    logger.debug("Phase 2b completed: %d narratives", len(result2b.data))

    # Extract narratives for TickResult
    self._narratives: dict[str, str] = {}
    for loc_id, data in result2b.data.items():
        self._narratives[loc_id] = data.get("narrative", "")

    # Phase 3: Apply results (pass master_results from phase 2a)
    result3 = await execute_phase3(simulation, self._config, result2a.data)
    if not result3.success:
        raise PhaseError("phase3", result3.error or "Unknown error")
    logger.debug("Phase 3 completed")

    # Phase 4: Memory update (pass pending_memories from phase 3)
    pending_memories = result3.data["pending_memories"]
    result4 = await execute_phase4(simulation, self._config, llm_client, pending_memories)
    if not result4.success:
        raise PhaseError("phase4", result4.error or "Unknown error")
    logger.debug("Phase 4 completed")
```

Remove all `# type: ignore` comments from phase calls.

### 6. Write unit tests `tests/unit/test_phase3.py`

Create comprehensive tests per spec. Key test cases:

- Character updates (location, internal_state, external_intent)
- Location updates (moment, description, null handling)
- Memory collection (pending_memories populated correctly)
- Validation fallbacks (invalid location_id, char_id, target location)
- Edge cases (empty master_results, multiple locations)
- Mutation verification (simulation changed in place)
- Console output verification (print called with ⚠️)

### 7. Update `tests/unit/test_runner.py`

Update mocks to handle new signatures:
- Phase 3 mock should accept `master_results` parameter
- Phase 4 mock should accept `pending_memories` parameter

## Testing

After implementation, run:

```bash
# Activate virtual environment
source venv/bin/activate  # or appropriate command

# Code quality
ruff check src/phases/phase3.py src/phases/phase2a.py src/runner.py
ruff format src/phases/phase3.py src/phases/phase2a.py src/runner.py
mypy src/phases/phase3.py src/phases/phase2a.py src/runner.py

# Unit tests
pytest tests/unit/test_phase3.py -v
pytest tests/unit/test_runner.py -v

# All tests to ensure no regressions
pytest tests/unit/ -v
```

**Expected results:**
- All quality checks pass
- All new tests pass
- Existing tests still pass (runner tests may need mock updates)

## Deliverables

1. `src/phases/phase2a.py` — added Pydantic models (CharacterUpdate, LocationUpdate, MasterOutput)
2. `src/phases/phase3.py` — full implementation
3. `src/phases/phase4.py` — updated signature with pending_memories
4. `src/phases/__init__.py` — updated exports
5. `src/runner.py` — updated phase calls, no type: ignore
6. `tests/unit/test_phase3.py` — comprehensive tests
7. `tests/unit/test_runner.py` — updated mocks (if needed)
8. `docs/specs/phase_3.md` — update status to READY
9. `docs/tasks/TS-B.2-PHASE3-001_REPORT.md` — execution report
