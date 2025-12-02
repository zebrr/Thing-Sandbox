# TS-B.0b-STUBS-001: Phase Stubs Implementation

## References

Before starting, read these documents:

1. `docs/specs/core_runner.md` — phase interface (`PhaseResult`, `execute()` signature)
2. `docs/specs/util_storage.md` — `Simulation`, `Character`, `Location` models
3. `src/schemas/IntentionResponse.schema.json` — phase1 output format
4. `src/schemas/Master.schema.json` — phase2a output format
5. `src/schemas/NarrativeResponse.schema.json` — phase2b output format

## Context

**Current status:** B.0a complete — core specs exist, SimulationConfig implemented.

**Goal:** Create stub implementations for all 5 phases. These stubs return hardcoded minimal data, enabling the skeleton system (B.0c) to run without LLM calls.

Stubs are temporary — they will be replaced with real implementations in later phases (B.1b, B.2, B.3b, B.4b).

## Phase Interface

All phases must implement this interface (from `core_runner.md`):

```python
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
) -> PhaseResult
```

Where:

```python
@dataclass
class PhaseResult:
    success: bool
    data: Any  # phase-specific, see below
    error: str | None = None
```

**Note:** Stubs don't use `llm_client`, but accept it for interface consistency.

## Steps

### 1. Create `src/phases/__init__.py`

Create new package for phase modules:

```python
"""Phase implementations for Thing' Sandbox simulation."""

from src.phases.phase1 import execute as execute_phase1
from src.phases.phase2a import execute as execute_phase2a
from src.phases.phase2b import execute as execute_phase2b
from src.phases.phase3 import execute as execute_phase3
from src.phases.phase4 import execute as execute_phase4

__all__ = [
    "execute_phase1",
    "execute_phase2a",
    "execute_phase2b",
    "execute_phase3",
    "execute_phase4",
]
```

### 2. Create `src/phases/common.py`

Shared types for phases:

```python
"""Common types for phase modules."""

from dataclasses import dataclass
from typing import Any


@dataclass
class PhaseResult:
    """Result of phase execution."""
    
    success: bool
    data: Any
    error: str | None = None
```

### 3. Create `src/phases/phase1.py` — Intentions Stub

Returns hardcoded intention for each character.

**Output `data`:** `dict[str, IntentionResponse]` — character_id → intention

```python
"""Phase 1: Character intentions (STUB)."""

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.storage import Simulation

# Type alias for clarity (actual Pydantic model will come in B.1b)
IntentionResponse = dict[str, str]


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: object,  # Unused in stub
) -> PhaseResult:
    """Generate intentions for all characters (stub: returns 'idle' for everyone)."""
    intentions: dict[str, IntentionResponse] = {}
    
    for char_id in simulation.characters:
        intentions[char_id] = {"intention": "idle"}
    
    return PhaseResult(success=True, data=intentions)
```

### 4. Create `src/phases/phase2a.py` — Arbitration Stub

Returns minimal Master output for each location.

**Output `data`:** `dict[str, MasterOutput]` — location_id → master result

```python
"""Phase 2a: Scene arbitration (STUB)."""

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.storage import Simulation

# Type alias (actual Pydantic model will come in B.3b)
MasterOutput = dict


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: object,  # Unused in stub
) -> PhaseResult:
    """Resolve scenes in all locations (stub: no changes)."""
    results: dict[str, MasterOutput] = {}
    
    for loc_id, location in simulation.locations.items():
        # Find characters in this location
        chars_here = {
            char_id: char
            for char_id, char in simulation.characters.items()
            if char.state.location == loc_id
        }
        
        # Build minimal Master output
        char_updates = {}
        for char_id, char in chars_here.items():
            char_updates[char_id] = {
                "location": char.state.location,  # No movement
                "internal_state": char.state.internal_state or "",
                "external_intent": char.state.external_intent or "",
                "memory_entry": "[Stub] Nothing notable happened.",
            }
        
        results[loc_id] = {
            "tick": simulation.current_tick,
            "location_id": loc_id,
            "characters": char_updates,
            "location": {
                "moment": None,  # No change
                "description": None,  # No change
            },
        }
    
    return PhaseResult(success=True, data=results)
```

### 5. Create `src/phases/phase2b.py` — Narrative Stub

Returns hardcoded narrative for each location.

**Output `data`:** `dict[str, NarrativeResponse]` — location_id → narrative

```python
"""Phase 2b: Narrative generation (STUB)."""

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.storage import Simulation

# Type alias (actual Pydantic model will come in B.3b)
NarrativeResponse = dict[str, str]


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: object,  # Unused in stub
) -> PhaseResult:
    """Generate narratives for all locations (stub: placeholder text)."""
    narratives: dict[str, NarrativeResponse] = {}
    
    for loc_id, location in simulation.locations.items():
        narratives[loc_id] = {
            "narrative": f"[Stub] Silence hangs over {location.identity.name}."
        }
    
    return PhaseResult(success=True, data=narratives)
```

### 6. Create `src/phases/phase3.py` — Apply Results Stub

In real implementation, applies Master output to simulation state. Stub does nothing.

**Output `data`:** `None`

```python
"""Phase 3: Apply arbitration results (STUB)."""

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.storage import Simulation


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: object,  # Unused (phase 3 never uses LLM)
) -> PhaseResult:
    """Apply Master results to simulation state (stub: no-op)."""
    # Real implementation will:
    # - Update character locations
    # - Update character internal_state, external_intent
    # - Add memory_entry to character memory
    # - Update location moment/description
    
    return PhaseResult(success=True, data=None)
```

### 7. Create `src/phases/phase4.py` — Memory Update Stub

In real implementation, performs FIFO shift and summarization. Stub does nothing.

**Output `data`:** `None`

```python
"""Phase 4: Memory update (STUB)."""

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.storage import Simulation


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: object,  # Unused in stub
) -> PhaseResult:
    """Update character memories (stub: no-op)."""
    # Real implementation will:
    # - FIFO shift memory cells
    # - Summarize evicted cell into summary (LLM call)
    # - Add new memory_entry to cell 0
    
    return PhaseResult(success=True, data=None)
```

## Testing

### Activate venv first:
```bash
# macOS
source venv/bin/activate
```

### Quality checks:
```bash
ruff check src/phases/
ruff format src/phases/
mypy src/phases/
```

### Unit tests

Create `tests/unit/test_phases_stub.py`:

```python
"""Tests for phase stubs."""

import pytest
from pathlib import Path

from src.config import Config
from src.utils.storage import load_simulation
from src.phases import (
    execute_phase1,
    execute_phase2a,
    execute_phase2b,
    execute_phase3,
    execute_phase4,
)


@pytest.fixture
def demo_sim():
    """Load demo simulation."""
    return load_simulation(Path("simulations/demo-sim"))


@pytest.fixture
def config():
    """Load config."""
    return Config.load()


@pytest.mark.asyncio
async def test_phase1_returns_intentions_for_all_characters(demo_sim, config):
    """Phase 1 stub returns intention for each character."""
    result = await execute_phase1(demo_sim, config, None)
    
    assert result.success is True
    assert result.error is None
    assert isinstance(result.data, dict)
    
    # Should have intention for each character
    for char_id in demo_sim.characters:
        assert char_id in result.data
        assert result.data[char_id]["intention"] == "idle"


@pytest.mark.asyncio
async def test_phase2a_returns_master_for_all_locations(demo_sim, config):
    """Phase 2a stub returns Master output for each location."""
    result = await execute_phase2a(demo_sim, config, None)
    
    assert result.success is True
    assert isinstance(result.data, dict)
    
    # Should have result for each location
    for loc_id in demo_sim.locations:
        assert loc_id in result.data
        assert result.data[loc_id]["location_id"] == loc_id
        assert "characters" in result.data[loc_id]
        assert "location" in result.data[loc_id]


@pytest.mark.asyncio
async def test_phase2b_returns_narratives_for_all_locations(demo_sim, config):
    """Phase 2b stub returns narrative for each location."""
    result = await execute_phase2b(demo_sim, config, None)
    
    assert result.success is True
    assert isinstance(result.data, dict)
    
    for loc_id in demo_sim.locations:
        assert loc_id in result.data
        assert "narrative" in result.data[loc_id]
        assert "[Stub]" in result.data[loc_id]["narrative"]


@pytest.mark.asyncio
async def test_phase3_succeeds_with_no_op(demo_sim, config):
    """Phase 3 stub succeeds and returns None data."""
    result = await execute_phase3(demo_sim, config, None)
    
    assert result.success is True
    assert result.data is None
    assert result.error is None


@pytest.mark.asyncio
async def test_phase4_succeeds_with_no_op(demo_sim, config):
    """Phase 4 stub succeeds and returns None data."""
    result = await execute_phase4(demo_sim, config, None)
    
    assert result.success is True
    assert result.data is None
    assert result.error is None


@pytest.mark.asyncio
async def test_phase1_handles_empty_simulation(config):
    """Phase 1 handles simulation with no characters."""
    from src.utils.storage import Simulation
    from datetime import datetime
    
    empty_sim = Simulation(
        id="empty",
        current_tick=0,
        created_at=datetime.now(),
        status="paused",
        characters={},
        locations={},
    )
    
    result = await execute_phase1(empty_sim, config, None)
    
    assert result.success is True
    assert result.data == {}
```

### Run tests:
```bash
pytest tests/unit/test_phases_stub.py -v
```

### Verify demo-sim loads correctly:
```bash
python -c "from src.utils.storage import load_simulation; from pathlib import Path; s = load_simulation(Path('simulations/demo-sim')); print(f'Loaded: {s.id}, {len(s.characters)} chars, {len(s.locations)} locs')"
```

Expected output:
```
Loaded: demo-sim, 2 chars, 2 locs
```

## Deliverables

1. **New files:**
   - `src/phases/__init__.py`
   - `src/phases/common.py`
   - `src/phases/phase1.py`
   - `src/phases/phase2a.py`
   - `src/phases/phase2b.py`
   - `src/phases/phase3.py`
   - `src/phases/phase4.py`
   - `tests/unit/test_phases_stub.py`

2. **Quality gates passed:**
   - `ruff check` — no errors
   - `ruff format` — formatted
   - `mypy` — no type errors
   - `pytest` — all tests pass

3. **Report:** `docs/tasks/TS-B.0b-STUBS-001_REPORT.md`
