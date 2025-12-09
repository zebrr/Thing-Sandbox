# TS-REFACTOR-NARR-002: Add simulation parameter to on_tick_start

## References

- `docs/specs/core_narrators.md` — Narrator protocol specification
- `docs/specs/core_runner.md` — TickRunner specification
- `src/narrators.py` — current implementation
- `src/runner.py` — current implementation
- `docs/tasks/TS-REFACTOR-NARR.md` — previous refactoring task

## Context

В TS-REFACTOR-NARR мы добавили lifecycle методы `on_tick_start` и `on_phase_complete` в Narrator protocol. Однако не учли, что TelegramNarrator (будущая реализация) потребует доступ к simulation для получения имён персонажей и локаций при форматировании сообщений.

**Текущая сигнатура:**
```python
def on_tick_start(self, sim_id: str, tick_number: int) -> None:
```

**Нужная сигнатура:**
```python
def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
```

Это позволит TelegramNarrator сохранить simulation в `self._simulation` и использовать в `on_phase_complete` для доступа к `simulation.characters[id].identity.name` и `simulation.locations[id].identity.name`.

## Steps

### 1. Update `src/narrators.py`

**Update imports:**
```python
if TYPE_CHECKING:
    from src.runner import PhaseData, TickReport
    from src.utils.storage import Simulation
```

**Update Narrator Protocol:**
```python
def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
    """Called when tick execution begins.

    Args:
        sim_id: Simulation identifier.
        tick_number: Tick number about to execute (current_tick + 1).
        simulation: Simulation instance with characters and locations.
    """
    ...
```

**Update ConsoleNarrator:**
```python
def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
    """No-op implementation for tick start event.

    Args:
        sim_id: Simulation identifier.
        tick_number: Tick number about to execute.
        simulation: Simulation instance (ignored).
    """
    pass
```

### 2. Update `src/runner.py`

**Update `_notify_tick_start` method:**
```python
def _notify_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
    """Notify all narrators that tick is starting.

    Narrator failures are logged but don't affect tick execution.

    Args:
        sim_id: Simulation identifier.
        tick_number: Tick number about to execute.
        simulation: Simulation instance.
    """
    for narrator in self._narrators:
        try:
            narrator.on_tick_start(sim_id, tick_number, simulation)
        except Exception as e:
            logger.error("Narrator %s on_tick_start failed: %s", type(narrator).__name__, e)
```

**Update call site in `run_tick`:**
```python
# Step 3b: Notify narrators of tick start
self._notify_tick_start(sim_id, simulation.current_tick + 1, simulation)
```

### 3. Update specs

**Update `docs/specs/core_narrators.md`:**

In Narrator Protocol section:
```python
def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
    """Called when tick execution begins."""
    ...
```

Update `Narrator.on_tick_start` documentation:
```
#### Narrator.on_tick_start(sim_id: str, tick_number: int, simulation: Simulation) -> None

Called when tick execution begins (after status set to "running").

- **Input**:
  - sim_id — Simulation identifier
  - tick_number — Tick number about to execute (current_tick + 1)
  - simulation — Simulation instance with characters and locations
- **Side effects**: Implementation-specific (e.g., storing simulation reference)
- **Note**: Default implementations should be no-op
```

Update Dependencies section — add `utils.storage (Simulation — via TYPE_CHECKING)`.

**Update `docs/specs/core_runner.md`:**

Update `_notify_tick_start` in Internal Methods section:
```
### _notify_tick_start(sim_id: str, tick_number: int, simulation: Simulation) -> None

Notify all narrators that tick is starting.

- **Input**:
  - sim_id — Simulation identifier
  - tick_number — Tick number about to execute
  - simulation — Simulation instance
- **Side effects**: Calls `on_tick_start` on each narrator
- **Error handling**: Narrator exceptions are caught, logged, and don't affect tick execution
```

### 4. Update tests

**Update `tests/unit/test_narrators.py`:**

Add MockSimulation:
```python
@dataclass
class MockSimulation:
    """Mock Simulation for testing narrators without importing storage."""
    id: str = "test-sim"
    current_tick: int = 0
    characters: dict = field(default_factory=dict)
    locations: dict = field(default_factory=dict)
```

Update `test_custom_narrator_satisfies_protocol`:
```python
def test_custom_narrator_satisfies_protocol(self) -> None:
    """Custom class with all protocol methods satisfies Narrator protocol."""

    class CustomNarrator:
        def output(self, report: MockTickReport) -> None:
            pass

        def on_tick_start(self, sim_id: str, tick_number: int, simulation: MockSimulation) -> None:
            pass

        def on_phase_complete(self, phase_name: str, phase_data: MockPhaseData) -> None:
            pass

    narrator: Narrator = CustomNarrator()  # type: ignore[assignment]
    assert hasattr(narrator, "output")
    assert hasattr(narrator, "on_tick_start")
    assert hasattr(narrator, "on_phase_complete")
```

Update `test_console_narrator_on_tick_start_noop`:
```python
def test_console_narrator_on_tick_start_noop(self) -> None:
    """on_tick_start does nothing but doesn't raise."""
    narrator = ConsoleNarrator()
    simulation = MockSimulation()
    narrator.on_tick_start("test-sim", 42, simulation)  # type: ignore[arg-type]
```

**Update `tests/unit/test_runner.py`:**

Update `test_runner_calls_on_tick_start`:
```python
async def test_runner_calls_on_tick_start(self, mock_config: Config, tmp_path: Path) -> None:
    """Runner calls on_tick_start on all narrators with simulation."""
    sim_path = create_test_simulation_on_disk(tmp_path)
    simulation = load_simulation(sim_path)

    captured_tick_starts: list[tuple[str, int, object]] = []

    class MockNarrator:
        def output(self, report: TickReport) -> None:
            pass

        def on_tick_start(self, sim_id: str, tick_number: int, simulation: object) -> None:
            captured_tick_starts.append((sim_id, tick_number, simulation))

        def on_phase_complete(self, phase_name: str, phase_data: object) -> None:
            pass

    # ... rest of test with mocked phases ...

    # Verify simulation was passed
    assert len(captured_tick_starts) == 2  # two narrators
    for sim_id, tick_number, sim in captured_tick_starts:
        assert sim_id == "test-sim"
        assert tick_number == 1
        assert sim is not None  # simulation object was passed
```

Update `test_runner_narrator_on_tick_start_error_isolated` — ensure FailingNarrator has correct signature:
```python
def on_tick_start(self, sim_id: str, tick_number: int, simulation: object) -> None:
    raise RuntimeError("on_tick_start crashed")
```

## Testing

### Quality checks (run first)
```bash
cd /Users/askold.romanov/code/thing-sandbox
source .venv/bin/activate
ruff check src/narrators.py src/runner.py
ruff format src/narrators.py src/runner.py
mypy src/narrators.py src/runner.py
```

### Run all tests
```bash
pytest tests/ -v
```

All existing tests must pass. Updated tests must pass.

## Deliverables

1. Modified `src/narrators.py` — updated protocol and ConsoleNarrator signature
2. Modified `src/runner.py` — updated `_notify_tick_start` method and call
3. Updated `docs/specs/core_narrators.md`
4. Updated `docs/specs/core_runner.md`
5. Updated `tests/unit/test_narrators.py`
6. Updated `tests/unit/test_runner.py`
7. All tests pass
8. Report in `docs/tasks/TS-REFACTOR-NARR-002_REPORT.md`
