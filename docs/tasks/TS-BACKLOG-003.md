# TS-BACKLOG-003: Migrate TickResult → TickReport

## References

Read before starting:
- `docs/specs/core_runner.md` — current TickResult definition and run_tick flow
- `docs/specs/core_tick_logger.md` — current PhaseData and TickReport definitions
- `docs/specs/core_narrators.md` — Narrator protocol and TickResult usage
- `src/runner.py` — implementation to modify
- `src/tick_logger.py` — implementation to modify
- `src/narrators.py` — implementation to modify

## Context

### Current State

We have two separate dataclasses for tick execution results:

**TickResult** (runner.py) — lightweight, for narrators:
```python
@dataclass
class TickResult:
    sim_id: str
    tick_number: int
    narratives: dict[str, str]
    location_names: dict[str, str]
    success: bool
    error: str | None = None
```

**TickReport** (tick_logger.py) — full data, for logging:
```python
@dataclass
class TickReport:
    sim_id: str
    tick_number: int
    timestamp: datetime
    duration: float
    narratives: dict[str, str]
    phases: dict[str, PhaseData]
    simulation: Simulation
    pending_memories: dict[str, str]
```

**PhaseData** (tick_logger.py):
```python
@dataclass
class PhaseData:
    duration: float
    stats: BatchStats | None
    data: Any
```

### Problem

- Duplication: sim_id, tick_number, narratives exist in both
- Artificial separation: runner creates both objects with overlapping data
- Future narrators (Telegram) will need fields from TickReport (duration, stats)
- PhaseData and TickReport logically belong to runner, not tick_logger

### Goal

Unify into single **TickReport** in `runner.py`:
- Move PhaseData to runner.py
- Extend TickResult with TickReport fields → rename to TickReport
- tick_logger.py imports from runner
- narrators.py imports TickReport from runner
- All outputs remain exactly the same (no visual changes)

## Steps

### Step 1: Modify runner.py

1.1. Add PhaseData dataclass (move from tick_logger.py):
```python
@dataclass
class PhaseData:
    """Data from single phase execution.

    Attributes:
        duration: Phase execution time in seconds.
        stats: LLM statistics from phase execution, None for Phase 3.
        data: Phase-specific output data.
    """
    duration: float
    stats: BatchStats | None
    data: Any
```

1.2. Rename and extend TickResult → TickReport:
```python
@dataclass
class TickReport:
    """Complete tick execution result.

    Used by both narrators (for output) and tick_logger (for detailed logs).

    Attributes:
        sim_id: Simulation identifier.
        tick_number: Completed tick number.
        narratives: Location_id to narrative text mapping.
        location_names: Location_id to display name mapping.
        success: Whether tick completed successfully.
        error: Error message if success is False.
        timestamp: Tick completion time (local).
        duration: Total tick execution time in seconds.
        phases: Phase name to PhaseData mapping.
        simulation: Simulation state after all phases.
        pending_memories: Character_id to memory text from Phase 3.
    """
    # Core (used by all consumers)
    sim_id: str
    tick_number: int
    narratives: dict[str, str]
    
    # For narrators
    location_names: dict[str, str]
    success: bool
    error: str | None = None
    
    # For tick_logger
    timestamp: datetime
    duration: float
    phases: dict[str, PhaseData]
    simulation: Simulation
    pending_memories: dict[str, str]
```

1.3. Add `datetime` import at top of file.

1.4. Update `run_tick()` method:
- Remove separate TickResult creation
- Create single TickReport with all fields
- Pass TickReport to narrators (instead of TickResult)
- Pass same TickReport to TickLogger

Find this section (around line 180-210) and refactor:
```python
# OLD: Creates TickReport for logger, then TickResult for narrators
# NEW: Create single TickReport, use for both
```

1.5. Update type hints and docstrings referencing TickResult → TickReport.

### Step 2: Modify tick_logger.py

2.1. Remove PhaseData class definition (moved to runner).

2.2. Remove TickReport class definition (moved to runner).

2.3. Update imports at top of file:
```python
# Add import from runner
from src.runner import PhaseData, TickReport
```

2.4. Remove local imports that are no longer needed if any.

2.5. Update TYPE_CHECKING imports if needed.

2.6. TickLogger class and all _format_* methods remain unchanged — they already expect TickReport.

### Step 3: Modify narrators.py

3.1. Update import:
```python
# OLD
if TYPE_CHECKING:
    from src.runner import TickResult

# NEW
if TYPE_CHECKING:
    from src.runner import TickReport
```

3.2. Update Narrator protocol:
```python
class Narrator(Protocol):
    def output(self, result: TickReport) -> None:
        ...
```

3.3. Update ConsoleNarrator.output() signature:
```python
def output(self, result: TickReport) -> None:
```

3.4. Update _print_output() signature:
```python
def _print_output(self, result: TickReport) -> None:
```

3.5. Update docstrings referencing TickResult → TickReport.

### Step 4: Update Tests

#### 4.1. tests/unit/test_runner.py

- Rename TestTickResult class → TestTickReport
- Update all TickResult references → TickReport
- Add new required fields to test fixtures:
  - timestamp (use `datetime.now()`)
  - duration (use `0.0` or appropriate float)
  - phases (use `{}` empty dict)
  - simulation (create minimal mock or use existing sample_simulation fixture)
  - pending_memories (use `{}` empty dict)
- Update test method names if they reference TickResult

#### 4.2. tests/unit/test_tick_logger.py

- Update imports: PhaseData and TickReport now from runner
- Remove local MockPhaseData if exists (use real PhaseData from runner)
- Update fixture imports
- Verify all mock_tick_report fixtures have all required fields

#### 4.3. tests/unit/test_narrators.py

- Rename MockTickResult → MockTickReport
- Add new fields to MockTickReport:
```python
@dataclass
class MockTickReport:
    sim_id: str
    tick_number: int
    narratives: dict[str, str]
    location_names: dict[str, str]
    success: bool
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0
    phases: dict = field(default_factory=dict)
    simulation: Any = None
    pending_memories: dict = field(default_factory=dict)
```
- Update all test methods creating MockTickResult → MockTickReport
- Update type ignore comments if needed

### Step 5: Update Specs

#### 5.1. docs/specs/core_runner.md

- Add PhaseData section (copy from core_tick_logger.md, adjust)
- Rename TickResult → TickReport in Public API section
- Add new fields to TickReport definition
- Update run_tick flow description (single TickReport creation)
- Update Usage Examples
- Update Test Coverage section

#### 5.2. docs/specs/core_tick_logger.md

- Remove PhaseData section (reference runner.py)
- Remove TickReport section (reference runner.py)
- Add note about imports from runner
- Update Dependencies section
- Update Usage Examples (imports)

#### 5.3. docs/specs/core_narrators.md

- Replace all TickResult → TickReport
- Update import in examples (from runner import TickReport)
- Update Narrator Protocol signature
- Update Usage Examples

## Testing

After all changes, run in order:

```bash
# Activate venv first
source .venv/bin/activate  # or appropriate for your OS

# 1. Code quality
ruff check src/ tests/
ruff format src/ tests/
mypy src/

# 2. Unit tests for modified modules
pytest tests/unit/test_runner.py -v
pytest tests/unit/test_tick_logger.py -v
pytest tests/unit/test_narrators.py -v

# 3. Full test suite
pytest

# 4. Manual verification (optional)
python -m src.cli reset war-of-the-worlds
python -m src.cli run war-of-the-worlds
# Verify console output looks exactly the same as before
# Verify logs/tick_000001.md is created and formatted correctly
```

### Expected Results

- All unit tests pass
- No ruff errors
- No mypy errors
- Console output format unchanged
- Log file format unchanged

## Deliverables

1. **Modified files:**
   - `src/runner.py` — PhaseData added, TickResult → TickReport
   - `src/tick_logger.py` — imports from runner, no local dataclasses
   - `src/narrators.py` — TickReport import and type hints

2. **Modified tests:**
   - `tests/unit/test_runner.py`
   - `tests/unit/test_tick_logger.py`
   - `tests/unit/test_narrators.py`

3. **Modified specs:**
   - `docs/specs/core_runner.md`
   - `docs/specs/core_tick_logger.md`
   - `docs/specs/core_narrators.md`

4. **Report:** `docs/tasks/TS-BACKLOG-003_REPORT.md` with:
   - Summary of changes made
   - Any issues encountered
   - Test results
   - Confirmation that outputs remain unchanged
