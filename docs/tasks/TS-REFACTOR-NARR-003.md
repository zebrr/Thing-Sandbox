# TS-REFACTOR-NARR-003: Make lifecycle methods async with fire-and-forget pattern

## References

- `docs/specs/core_narrators.md` — Narrator protocol specification
- `docs/specs/core_runner.md` — TickRunner specification
- `src/narrators.py` — current implementation
- `src/runner.py` — current implementation
- `docs/tasks/TS-REFACTOR-NARR.md` — first refactoring (added lifecycle methods)
- `docs/tasks/TS-REFACTOR-NARR-002.md` — second refactoring (added simulation param)

## Context

Lifecycle методы протокола Narrator сейчас sync, но TelegramClient — async. Нам нужно:
1. Сделать lifecycle методы async
2. Не блокировать фазы ожиданием Telegram
3. Дождаться завершения всех отправок в конце тика

**Паттерн fire-and-forget с await в конце:**
```
Phase 1 done → create_task(on_phase_complete)  # не ждём
Phase 2b done → create_task(on_phase_complete)  # не ждём
...фазы идут параллельно с отправкой...
Save to disk
await gather(all_tasks, timeout=30)  # один раз в конце
```

В нормальном сценарии к концу тика Telegram уже ответил (фазы идут ~10 сек, этого достаточно). Timeout 30 сек — страховка на случай проблем с сетью.

## Steps

### 1. Update `src/narrators.py`

**Update Narrator Protocol:**
```python
class Narrator(Protocol):
    def output(self, report: TickReport) -> None:
        """Output tick report to destination."""
        ...

    async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
        """Called when tick execution begins."""
        ...

    async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """Called after each phase completes successfully."""
        ...
```

**Update ConsoleNarrator:**
```python
async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
    """No-op implementation for tick start event."""
    pass

async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
    """No-op implementation for phase complete event."""
    pass
```

### 2. Update `src/runner.py`

**Add import:**
```python
import asyncio
```

**Add constant for timeout:**
```python
NARRATOR_TIMEOUT = 30.0  # seconds to wait for narrator tasks at end of tick
```

**Add instance attribute in run_tick (after status check):**
```python
# Initialize pending narrator tasks
self._pending_narrator_tasks: list[asyncio.Task] = []
```

**Update `_notify_tick_start` — make async, await directly (no network, fast):**
```python
async def _notify_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
    """Notify all narrators that tick is starting.

    Called synchronously (awaited) because it's fast and narrators may need
    to store simulation reference before phases run.
    """
    for narrator in self._narrators:
        try:
            await narrator.on_tick_start(sim_id, tick_number, simulation)
        except Exception as e:
            logger.error("Narrator %s on_tick_start failed: %s", type(narrator).__name__, e)
```

**Update `_notify_phase_complete` — fire-and-forget pattern:**
```python
def _notify_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
    """Schedule narrator notifications for phase completion.

    Uses fire-and-forget pattern: creates tasks but doesn't await them.
    Tasks are collected in self._pending_narrator_tasks and awaited
    at end of tick via _await_pending_narrator_tasks().
    """
    for narrator in self._narrators:
        task = asyncio.create_task(
            self._safe_phase_complete(narrator, phase_name, phase_data)
        )
        self._pending_narrator_tasks.append(task)

async def _safe_phase_complete(
    self, narrator: Narrator, phase_name: str, phase_data: PhaseData
) -> None:
    """Wrapper to catch exceptions from narrator.on_phase_complete."""
    try:
        await narrator.on_phase_complete(phase_name, phase_data)
    except Exception as e:
        logger.error("Narrator %s on_phase_complete failed: %s", type(narrator).__name__, e)
```

**Add new method to await all pending tasks:**
```python
async def _await_pending_narrator_tasks(self) -> None:
    """Wait for all pending narrator tasks with timeout.

    Called at end of tick after save. In normal scenario tasks are already
    done (phases take ~10s, enough for Telegram). Timeout is safety net.
    """
    if not self._pending_narrator_tasks:
        return

    try:
        await asyncio.wait_for(
            asyncio.gather(*self._pending_narrator_tasks, return_exceptions=True),
            timeout=NARRATOR_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Narrator tasks timed out after %.1fs (%d tasks pending)",
            NARRATOR_TIMEOUT,
            len([t for t in self._pending_narrator_tasks if not t.done()]),
        )
    finally:
        self._pending_narrator_tasks.clear()
```

**Update `run_tick` call sites:**

After status check, initialize tasks list:
```python
# Step 3: Set status to running (in memory)
simulation.status = "running"

# Initialize pending narrator tasks
self._pending_narrator_tasks = []

# Step 3b: Notify narrators of tick start (await - fast, no network)
await self._notify_tick_start(sim_id, simulation.current_tick + 1, simulation)
```

After save, before calling output():
```python
# Step 11: Save simulation
save_simulation(sim_path, simulation)

# Step 11b: Await pending narrator tasks (fire-and-forget завершаем здесь)
await self._await_pending_narrator_tasks()

# Step 12: Log tick completion with statistics
```

### 3. Update specs

**Update `docs/specs/core_narrators.md`:**

Protocol section:
```python
class Narrator(Protocol):
    def output(self, report: TickReport) -> None: ...
    async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None: ...
    async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None: ...
```

Update method docs to mention async nature and fire-and-forget pattern for on_phase_complete.

**Update `docs/specs/core_runner.md`:**

Update Tick Execution Flow:
```
3b. Notify narrators via await _notify_tick_start() — awaited, fast
6.1-6.5. After each phase: _notify_phase_complete() — fire-and-forget, creates tasks
11. Save simulation
11b. await _await_pending_narrator_tasks() — wait for narrator tasks with timeout
```

Add Internal Methods:
- `_safe_phase_complete(narrator, phase_name, phase_data)` — wrapper with exception handling
- `_await_pending_narrator_tasks()` — await all with timeout

Add constant: `NARRATOR_TIMEOUT = 30.0`

### 4. Update tests

**Update `tests/unit/test_narrators.py`:**

Update MockSimulation, keep as is.

Update tests to use async:
```python
@pytest.mark.asyncio
async def test_console_narrator_on_tick_start_noop() -> None:
    """on_tick_start does nothing but doesn't raise."""
    narrator = ConsoleNarrator()
    simulation = MockSimulation()
    await narrator.on_tick_start("test-sim", 42, simulation)  # type: ignore[arg-type]

@pytest.mark.asyncio
async def test_console_narrator_on_phase_complete_noop() -> None:
    """on_phase_complete does nothing but doesn't raise."""
    narrator = ConsoleNarrator()
    phase_data = MockPhaseData(duration=1.0, stats=None, data={})
    await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]
```

Update custom narrator test:
```python
def test_custom_narrator_satisfies_protocol() -> None:
    """Custom class with all protocol methods satisfies Narrator protocol."""

    class CustomNarrator:
        def output(self, report: MockTickReport) -> None:
            pass

        async def on_tick_start(self, sim_id: str, tick_number: int, simulation: MockSimulation) -> None:
            pass

        async def on_phase_complete(self, phase_name: str, phase_data: MockPhaseData) -> None:
            pass

    narrator: Narrator = CustomNarrator()  # type: ignore[assignment]
    assert hasattr(narrator, "output")
    assert hasattr(narrator, "on_tick_start")
    assert hasattr(narrator, "on_phase_complete")
```

**Update `tests/unit/test_runner.py`:**

Update MockNarrator classes to be async:
```python
class MockNarrator:
    def output(self, report: TickReport) -> None:
        pass

    async def on_tick_start(self, sim_id: str, tick_number: int, simulation: object) -> None:
        captured_tick_starts.append((sim_id, tick_number, simulation))

    async def on_phase_complete(self, phase_name: str, phase_data: object) -> None:
        captured_phase_completes.append(phase_name)
```

Add new tests:
```python
@pytest.mark.asyncio
async def test_runner_awaits_pending_tasks_at_end(self, mock_config, tmp_path):
    """Runner awaits all narrator tasks at end of tick."""
    # Create narrator with slow on_phase_complete
    # Verify tasks are awaited before run_tick returns

@pytest.mark.asyncio
async def test_runner_narrator_timeout_doesnt_block(self, mock_config, tmp_path):
    """Runner continues after narrator timeout."""
    # Create narrator that hangs forever
    # Verify run_tick completes after NARRATOR_TIMEOUT
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

## Deliverables

1. Modified `src/narrators.py` — async lifecycle methods
2. Modified `src/runner.py` — fire-and-forget pattern with await at end
3. Updated `docs/specs/core_narrators.md`
4. Updated `docs/specs/core_runner.md`
5. Updated `tests/unit/test_narrators.py`
6. Updated `tests/unit/test_runner.py`
7. All tests pass
8. Report in `docs/tasks/TS-REFACTOR-NARR-003_REPORT.md`
