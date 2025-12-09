# core_runner.md

## Status: READY

Tick orchestrator for Thing' Sandbox. Executes one complete tick of simulation:
loads state, runs all phases sequentially, saves results atomically.

---

## Public API

### PhaseData

Data from single phase execution, used by TickLogger.

```python
@dataclass
class PhaseData:
    duration: float              # phase execution time in seconds
    stats: BatchStats | None     # LLM statistics, None for Phase 3
    data: Any                    # phase-specific output data
```

### TickReport

Complete tick execution result. Used by both narrators (for output) and TickLogger (for detailed logs).

```python
@dataclass
class TickReport:
    # Required fields
    sim_id: str
    tick_number: int              # completed tick number
    narratives: dict[str, str]    # location_id → narrative text
    location_names: dict[str, str]  # location_id → display name
    success: bool
    timestamp: datetime           # tick completion time (local)
    duration: float               # total tick execution time in seconds
    phases: dict[str, PhaseData]  # phase name → PhaseData mapping
    simulation: Simulation        # simulation state after all phases
    pending_memories: dict[str, str]  # character_id → memory text from Phase 3
    # Optional field
    error: str | None = None
```

### TickRunner

Main orchestrator class.

#### TickRunner.__init__(config: Config, narrators: Sequence[Narrator]) -> None

Initialize tick runner.

- **Input**:
  - config — application configuration
  - narrators — sequence of output handlers
- **Attributes**:
  - _config — stored config reference
  - _narrators — stored narrators sequence

Note: Uses `load_simulation()` and `save_simulation()` functions directly from `utils.storage`.

#### Internal Attributes (set during run_tick)

- `_char_entities: list[dict[str, Any]]` — entity dicts for characters (mutated by LLMClient)
- `_loc_entities: list[dict[str, Any]]` — entity dicts for locations (mutated by LLMClient)
- `_tick_stats: BatchStats` — accumulated statistics for the tick
- `_narratives: dict[str, str]` — narratives extracted from phase 2b
- `_phase_data: dict[str, PhaseData]` — per-phase execution data for TickLogger
- `_pending_memories: dict[str, str]` — pending memory texts from phase 3 for TickLogger

#### TickRunner.run_tick(simulation: Simulation, sim_path: Path) -> TickReport

Execute one complete tick of simulation.

- **Input**:
  - simulation — loaded Simulation instance
  - sim_path — path to simulation folder (for saving state)
- **Returns**: TickReport with tick data, narratives, and phase information
- **Raises**:
  - SimulationBusyError (EXIT_RUNTIME_ERROR) — simulation status is "running"
  - PhaseError (EXIT_RUNTIME_ERROR) — any phase failed
  - StorageError (EXIT_IO_ERROR) — failed to save results
- **Side effects**:
  - Updates simulation state on disk (atomic)
  - Calls all narrators with TickReport
- **Note**: CLI is responsible for loading simulation and handling SimulationNotFoundError

---

## Tick Execution Flow

### Sequence

```
1. Receive simulation (already loaded by CLI)
2. Validate status == "paused"
3. Set status = "running" (in memory only)
3b. Notify narrators via _notify_tick_start(sim_id, tick_number, simulation)
4. Create entity dicts for LLM clients (_create_entity_dicts)
5. Initialize tick statistics (_tick_stats = BatchStats())
6. Execute phases (_execute_phases):
   6.1. Phase 1 — character intentions (N requests, char client)
        → Notify narrators via _notify_phase_complete("phase1", ...)
   6.2. Phase 2a — scene arbitration (L requests, loc client)
        → Notify narrators via _notify_phase_complete("phase2a", ...)
   6.3. Phase 2b — narrative generation (L requests, stub)
        → Notify narrators via _notify_phase_complete("phase2b", ...)
   6.4. Phase 3 — apply results (0 requests)
        → Notify narrators via _notify_phase_complete("phase3", ...)
   6.5. Phase 4 — memory update (N requests, char client)
        → Notify narrators via _notify_phase_complete("phase4", ...)
7. Sync _openai data back to simulation models (_sync_openai_data)
8. Aggregate usage into simulation._openai (_aggregate_simulation_usage)
9. Increment current_tick
10. Set status = "paused"
11. Save simulation atomically via save_simulation()
12. Log tick completion with statistics
12b. Build TickReport with narratives and phase data
13. Write tick log via TickLogger if output.file.enabled
14. Call each narrator with TickReport
15. Return TickReport
```

**Phase Data Collection:**
Each phase stores duration, stats, and output in `_phase_data[phase_name]` as PhaseData.
After save, TickLogger uses this data to write detailed markdown log.

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

## Internal Methods

### _create_entity_dicts(simulation: Simulation) -> None

Create entity dicts for LLM clients.

Converts Pydantic models to dicts and stores them as instance attributes (`_char_entities`, `_loc_entities`). These dicts are mutated by LLMClient during phase execution (adds `_openai` key with chains and usage).

### _create_char_llm_client(config: PhaseConfig) -> LLMClient

Create LLM client for character phases (1, 4).

Uses `_char_entities` for entity storage.

### _create_loc_llm_client(config: PhaseConfig) -> LLMClient

Create LLM client for location phases (2a, 2b).

Uses `_loc_entities` for entity storage.

### _sync_openai_data(simulation: Simulation) -> None

Copy `_openai` data from entity dicts back to Simulation models.

After phases execute, the entity dicts contain updated `_openai` data (chains and usage). This method copies that data back to the Pydantic models via `__pydantic_extra__` so it can be saved via `model_dump()`.

### _aggregate_simulation_usage(simulation: Simulation) -> None

Sum usage from all entities into `simulation._openai`.

Calculates total usage across all characters and locations:
```python
totals = {
    "total_tokens": 0,
    "reasoning_tokens": 0,
    "cached_tokens": 0,
    "total_requests": 0,
}
```

### _accumulate_tick_stats(phase_stats: BatchStats) -> None

Add phase statistics to tick totals (`_tick_stats`).

Called after each LLM-using phase to accumulate batch stats.

### _execute_phases(simulation: Simulation) -> None

Execute all phases sequentially.

Creates separate LLM clients for character and location phases. Logs statistics after each phase. Notifies narrators via `_notify_phase_complete` after each phase. Raises `PhaseError` if any phase returns `success=False`.

### _notify_tick_start(sim_id: str, tick_number: int, simulation: Simulation) -> None

Notify all narrators that tick is starting.

- **Input**:
  - sim_id — Simulation identifier
  - tick_number — Tick number about to execute
  - simulation — Simulation instance
- **Side effects**: Calls `on_tick_start` on each narrator
- **Error handling**: Narrator exceptions are caught, logged, and don't affect tick execution

### _notify_phase_complete(phase_name: str, phase_data: PhaseData) -> None

Notify all narrators that phase completed.

- **Input**:
  - phase_name — Name of completed phase (phase1, phase2a, phase2b, phase3, phase4)
  - phase_data — PhaseData with duration, stats, and output
- **Side effects**: Calls `on_phase_complete` on each narrator
- **Error handling**: Narrator exceptions are caught, logged, and don't affect tick execution

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

- **Standard Library**: asyncio, dataclasses, datetime, logging, time, typing (Any, TYPE_CHECKING)
- **External**: None
- **Internal**:
  - config (Config, PhaseConfig)
  - utils.storage (load_simulation, save_simulation, Simulation)
  - utils.llm (LLMClient, BatchStats)
  - utils.llm_adapters (OpenAIAdapter)
  - narrators (Narrator protocol)
  - phases (execute_phase1, execute_phase2a, execute_phase2b, execute_phase3, execute_phase4)
  - tick_logger (TickLogger — imports PhaseData and TickReport from runner)

---

## Usage Examples

### Basic Usage

```python
from pathlib import Path
from src.config import Config
from src.narrators import ConsoleNarrator
from src.runner import TickRunner
from src.utils.storage import load_simulation

config = Config.load()
narrators = [ConsoleNarrator()]

sim_path = config.project_root / "simulations" / "my-sim"
simulation = load_simulation(sim_path)

runner = TickRunner(config, narrators)
await runner.run_tick(simulation, sim_path)
```

### Error Handling

```python
from src.runner import TickRunner, PhaseError
from src.utils.storage import load_simulation, SimulationNotFoundError
from src.utils.exit_codes import EXIT_INPUT_ERROR, EXIT_RUNTIME_ERROR

# Loading is now done in CLI, which handles SimulationNotFoundError
try:
    simulation = load_simulation(sim_path)
except SimulationNotFoundError:
    sys.exit(EXIT_INPUT_ERROR)

try:
    await runner.run_tick(simulation, sim_path)
except PhaseError as e:
    logger.error("Phase failed: %s", e)
    sys.exit(EXIT_RUNTIME_ERROR)
```

---

## Test Coverage

### Unit Tests

- test_run_tick_success — full tick completes, state saved
- test_run_tick_simulation_busy — status "running" raises SimulationBusyError
- test_run_tick_phase1_fails — no state saved, exception propagates
- test_run_tick_phase2a_fails — no state saved after phase1 completed
- test_run_tick_atomicity — verify no partial saves
- test_run_tick_narrators_called — all narrators receive TickReport
- test_run_tick_empty_simulation — works with 0 characters
- test_run_tick_increments_tick_number — current_tick incremented

**_sync_openai_data Tests (TestSyncOpenaiData):**
- test_sync_copies_openai_to_characters — copies _openai from entity dicts to character models
- test_sync_copies_openai_to_locations — copies _openai from entity dicts to location models
- test_sync_creates_extra_if_none — creates __pydantic_extra__ if not present

**_aggregate_simulation_usage Tests (TestAggregateSimulationUsage):**
- test_aggregate_sums_all_entities — sums usage from all characters and locations
- test_aggregate_creates_extra_if_none — creates __pydantic_extra__ if not present

**Narrator Lifecycle Tests (TestNarratorLifecycleNotifications):**
- test_runner_calls_on_tick_start — verifies on_tick_start called on all narrators
- test_runner_calls_on_phase_complete_for_each_phase — verifies 5 calls (one per phase)
- test_runner_narrator_on_tick_start_error_isolated — error doesn't stop tick
- test_runner_narrator_on_phase_complete_error_isolated — error doesn't stop tick

### Integration Tests

- test_run_tick_with_stubs — full tick with stub phases
- test_run_tick_state_persistence — load after save matches
- test_run_tick_creates_log_file — log file written when output.file.enabled
- test_run_tick_log_file_disabled — no log file when output.file.enabled=False

---

## Implementation Notes

### Async Execution

Runner is async to support concurrent LLM calls within phases.
Phases may use `asyncio.gather()` for batch requests.

### Narrator Invocation

Narrators are called synchronously after successful save.
If narrator fails (e.g., Telegram API error), it's logged but doesn't affect tick result.

### Logging

**Per-Phase Logging (INFO):**
```
🎭 phase1: Complete (5 chars, 1,234 tokens, 456 reasoning)
⚖️ phase2a: Complete (3 locs, 2,345 tokens, 789 reasoning)
📖 phase2b: Complete (3 narratives, stub)
⚡ phase3: Complete (results applied)
🧠 phase4: Complete (5 chars, 987 tokens, 321 reasoning)
```

**Tick Completion (INFO):**
```
🎬 runner: Tick 42 complete (3.2s, 4,566 tokens, 1,566 reasoning)
```

- DEBUG: phase start/end times, tick timing, entity dict creation
- INFO: phase completion with stats, tick completion with stats
- ERROR: phase failures, storage errors
