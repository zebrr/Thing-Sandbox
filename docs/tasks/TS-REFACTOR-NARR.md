# TS-REFACTOR-NARR: Extend Narrator Protocol with Tick Lifecycle Events

## References

- `docs/specs/core_narrators.md` — current Narrator protocol specification
- `docs/specs/core_runner.md` — TickRunner specification, execution flow
- `src/narrators.py` — current implementation
- `src/runner.py` — current implementation

## Context

Currently, Narrator protocol has only one method `output(report: TickReport)` which is called after tick completes and state is saved to disk. This limits our ability to provide progress feedback during tick execution.

We want to extend the protocol to support tick lifecycle events:
- `on_tick_start` — called when tick execution begins
- `on_phase_complete` — called after each phase completes successfully

**Important constraints:**
- Existing behavior must NOT change — ConsoleNarrator should work exactly as before
- Disk atomicity is preserved — these are in-memory notifications only
- New methods have default no-op implementations

## Steps

### 1. Update `src/narrators.py`

**Extend Narrator Protocol:**
```python
class Narrator(Protocol):
    def output(self, report: TickReport) -> None:
        """Output tick report to destination."""
        ...
    
    def on_tick_start(self, sim_id: str, tick_number: int) -> None:
        """Called when tick execution begins.
        
        Args:
            sim_id: Simulation identifier.
            tick_number: Tick number about to execute (current_tick + 1).
        """
        ...
    
    def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """Called after each phase completes successfully.
        
        Args:
            phase_name: Name of completed phase (phase1, phase2a, phase2b, phase3, phase4).
            phase_data: Phase execution data including duration, stats, and output.
        """
        ...
```

**Add import for PhaseData** (use TYPE_CHECKING to avoid circular import):
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.runner import PhaseData
```

**Update ConsoleNarrator** — add no-op implementations:
```python
def on_tick_start(self, sim_id: str, tick_number: int) -> None:
    """No-op implementation for tick start event."""
    pass

def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
    """No-op implementation for phase complete event."""
    pass
```

### 2. Update `src/runner.py`

**Add notification helper methods:**
```python
def _notify_tick_start(self, sim_id: str, tick_number: int) -> None:
    """Notify all narrators that tick is starting.
    
    Args:
        sim_id: Simulation identifier.
        tick_number: Tick number about to execute.
    """
    for narrator in self._narrators:
        try:
            narrator.on_tick_start(sim_id, tick_number)
        except Exception as e:
            logger.error("Narrator %s on_tick_start failed: %s", type(narrator).__name__, e)

def _notify_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
    """Notify all narrators that phase completed.
    
    Args:
        phase_name: Name of completed phase.
        phase_data: Phase execution data.
    """
    for narrator in self._narrators:
        try:
            narrator.on_phase_complete(phase_name, phase_data)
        except Exception as e:
            logger.error("Narrator %s on_phase_complete failed: %s", type(narrator).__name__, e)
```

**Update `run_tick()` method** — add notification call after step 3 (status set to running):
```python
# After: simulation.status = "running"
# Add:
self._notify_tick_start(sim_id, simulation.current_tick + 1)
```

**Update `_execute_phases()` method** — add notification after each phase's PhaseData is stored:
```python
# After each: self._phase_data["phaseX"] = PhaseData(...)
# Add:
self._notify_phase_complete("phaseX", self._phase_data["phaseX"])
```

This applies to all 5 phases: phase1, phase2a, phase2b, phase3, phase4.

### 3. Update specs

**Update `docs/specs/core_narrators.md`:**
- Add `on_tick_start` and `on_phase_complete` to Narrator Protocol section
- Document that these methods have no-op defaults
- Add to ConsoleNarrator section that it implements no-ops
- Update Test Coverage section with new tests

**Update `docs/specs/core_runner.md`:**
- Update Tick Execution Flow to include narrator notification steps
- Update Internal Methods section with `_notify_tick_start` and `_notify_phase_complete`
- Update Test Coverage section with new tests

## Testing

### Quality checks (run first)
```bash
cd /Users/askold.romanov/code/thing-sandbox
source .venv/bin/activate
ruff check src/narrators.py src/runner.py
ruff format src/narrators.py src/runner.py
mypy src/narrators.py src/runner.py
```

### Run existing tests (must pass unchanged)
```bash
pytest tests/unit/test_narrators.py -v
pytest tests/unit/test_runner.py -v
pytest tests/integration/ -v
```

### Add new tests in `tests/unit/test_narrators.py`
```python
def test_console_narrator_on_tick_start_noop():
    """on_tick_start does nothing but doesn't raise."""
    narrator = ConsoleNarrator()
    narrator.on_tick_start("test-sim", 42)  # Should not raise

def test_console_narrator_on_phase_complete_noop():
    """on_phase_complete does nothing but doesn't raise."""
    narrator = ConsoleNarrator()
    phase_data = PhaseData(duration=1.0, stats=None, data={})
    narrator.on_phase_complete("phase1", phase_data)  # Should not raise
```

### Add new tests in `tests/unit/test_runner.py`
```python
def test_runner_calls_on_tick_start():
    """Runner calls on_tick_start on all narrators."""
    # Use mock narrator, verify on_tick_start called with correct args

def test_runner_calls_on_phase_complete_for_each_phase():
    """Runner calls on_phase_complete after each phase."""
    # Use mock narrator, verify on_phase_complete called 5 times
    # Verify phase names: phase1, phase2a, phase2b, phase3, phase4

def test_runner_narrator_on_tick_start_error_isolated():
    """Narrator error in on_tick_start doesn't stop tick execution."""
    # Use mock that raises, verify tick still completes

def test_runner_narrator_on_phase_complete_error_isolated():
    """Narrator error in on_phase_complete doesn't stop tick execution."""
    # Use mock that raises, verify tick still completes
```

### Run all tests
```bash
pytest tests/ -v
```

## Deliverables

1. Modified `src/narrators.py` with extended protocol and ConsoleNarrator no-ops
2. Modified `src/runner.py` with notification methods and calls
3. Updated `docs/specs/core_narrators.md`
4. Updated `docs/specs/core_runner.md`
5. New tests in `tests/unit/test_narrators.py`
6. New tests in `tests/unit/test_runner.py`
7. All existing tests pass
8. All new tests pass
9. Report in `docs/tasks/TS-REFACTOR-NARR_REPORT.md`
