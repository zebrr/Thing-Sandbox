# core_runner.md

## Status: NOT_STARTED

Tick orchestrator for Thing' Sandbox. Executes one complete tick of simulation:
loads state, runs all phases sequentially, saves results atomically.

---

## Public API

### TickResult

Result of a completed tick.

```python
@dataclass
class TickResult:
    sim_id: str
    tick_number: int              # completed tick number
    narratives: dict[str, str]    # location_id → narrative text
    success: bool
    error: str | None = None
```

### TickRunner

Main orchestrator class.

#### TickRunner.__init__(config: Config, storage: Storage, narrators: list[Narrator]) -> None

Initialize tick runner.

- **Input**:
  - config — application configuration
  - storage — simulation storage interface
  - narrators — list of output handlers
- **Attributes**:
  - _config — stored config reference
  - _storage — stored storage reference
  - _narrators — stored narrators list

#### TickRunner.run_tick(sim_id: str) -> TickResult

Execute one complete tick of simulation.

- **Input**:
  - sim_id — simulation identifier
- **Returns**: TickResult with tick data and narratives
- **Raises**:
  - SimulationNotFoundError (EXIT_INPUT_ERROR) — simulation doesn't exist
  - SimulationBusyError (EXIT_RUNTIME_ERROR) — simulation status is "running"
  - PhaseError (EXIT_RUNTIME_ERROR) — any phase failed
  - StorageError (EXIT_IO_ERROR) — failed to save results
- **Side effects**:
  - Updates simulation state on disk (atomic)
  - Calls all narrators with TickResult

---

## Tick Execution Flow

### Sequence

```
1. Load simulation via Storage
2. Validate status == "paused"
3. Set status = "running" (in memory only)
4. Execute phases:
   4.1. Phase 1 — character intentions (N requests)
   4.2. Phase 2a — scene arbitration (L requests)
   4.3. Phase 2b — narrative generation (L requests)
   4.4. Phase 3 — apply results (0 requests)
   4.5. Phase 4 — memory update (N requests)
5. Collect narratives into TickResult
6. Increment current_tick
7. Set status = "paused"
8. Save simulation atomically via Storage
9. Call each narrator with TickResult
10. Return TickResult
```

### Atomicity

- State is modified in memory during phases
- Disk write happens only after ALL phases complete successfully
- If any phase fails — no changes saved, simulation remains at previous tick
- Save order: characters → locations → logs → simulation.json

### Status Transitions

```
paused → running (step 3, in memory)
running → paused (step 7, in memory)
Save to disk (step 8)
```

If crash between steps 3-8: simulation.json still shows "paused" with old tick number.
Next run will re-execute the same tick from scratch.

---

## Phase Interface

Each phase module must implement:

```python
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,  # phases 1, 2a, 2b, 4
) -> PhaseResult
```

Phase 3 doesn't use LLMClient (pure mechanics).

### PhaseResult

```python
@dataclass
class PhaseResult:
    success: bool
    data: Any  # phase-specific output
    error: str | None = None
```

---

## Error Handling

### Exit Codes

Uses standard codes from `utils/exit_codes.py`:
- EXIT_INPUT_ERROR (2) — simulation not found
- EXIT_RUNTIME_ERROR (3) — phase failed, simulation busy
- EXIT_IO_ERROR (5) — storage write failed

### Error Propagation

Runner does NOT catch phase exceptions. Exceptions propagate to CLI which:
1. Logs the error
2. Returns appropriate exit code
3. Simulation state unchanged (atomicity guarantee)

### Boundary Cases

- Empty simulation (0 characters) — phases 1, 4 skip, phases 2a, 2b, 3 still run (world evolves)
- Single location — normal execution
- LLM timeout in any phase — exception propagates, no state saved

---

## Dependencies

- **Standard Library**: asyncio, dataclasses, logging
- **External**: None
- **Internal**: 
  - config (Config)
  - utils.storage (Storage, Simulation)
  - narrators (Narrator protocol)
  - phase1, phase2a, phase2b, phase3, phase4

---

## Usage Examples

### Basic Usage

```python
from src.config import Config
from src.utils.storage import Storage
from src.narrators import ConsoleNarrator
from src.runner import TickRunner

config = Config.load()
storage = Storage(config)
narrators = [ConsoleNarrator()]

runner = TickRunner(config, storage, narrators)
result = await runner.run_tick("my-sim")

print(f"Completed tick {result.tick_number}")
```

### Error Handling

```python
from src.runner import TickRunner, SimulationNotFoundError, PhaseError
from src.utils.exit_codes import EXIT_INPUT_ERROR, EXIT_RUNTIME_ERROR

try:
    result = await runner.run_tick("my-sim")
except SimulationNotFoundError:
    sys.exit(EXIT_INPUT_ERROR)
except PhaseError as e:
    print(f"Phase failed: {e}", file=sys.stderr)
    sys.exit(EXIT_RUNTIME_ERROR)
```

---

## Test Coverage

### Unit Tests

- test_run_tick_success — full tick completes, state saved
- test_run_tick_simulation_not_found — raises SimulationNotFoundError
- test_run_tick_simulation_busy — status "running" raises SimulationBusyError
- test_run_tick_phase1_fails — no state saved, exception propagates
- test_run_tick_phase2a_fails — no state saved after phase1 completed
- test_run_tick_atomicity — verify no partial saves
- test_run_tick_narrators_called — all narrators receive TickResult
- test_run_tick_empty_simulation — works with 0 characters
- test_run_tick_increments_tick_number — current_tick incremented

### Integration Tests

- test_run_tick_with_stubs — full tick with stub phases
- test_run_tick_state_persistence — load after save matches

---

## Implementation Notes

### Async Execution

Runner is async to support concurrent LLM calls within phases.
Phases may use `asyncio.gather()` for batch requests.

### Narrator Invocation

Narrators are called synchronously after successful save.
If narrator fails (e.g., Telegram API error), it's logged but doesn't affect tick result.

### Logging

- DEBUG: phase start/end times, tick timing
- INFO: tick completed successfully
- ERROR: phase failures, storage errors
