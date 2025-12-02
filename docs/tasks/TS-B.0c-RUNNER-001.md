# TS-B.0c-RUNNER-001: Runner + CLI + Narrators (Skeleton Assembly)

## References

**Must read before starting:**
- `docs/specs/core_runner.md` — TickRunner specification
- `docs/specs/core_cli.md` — CLI specification
- `docs/specs/core_narrators.md` — Narrator protocol specification
- `src/phases/__init__.py` — phase exports
- `src/phases/common.py` — PhaseResult dataclass
- `src/utils/storage.py` — Storage API, Simulation model, exceptions
- `src/utils/exit_codes.py` — exit code constants
- `src/config.py` — Config class (note: `_project_root` attribute)

**For context:**
- `docs/tasks/TS-B.0b-STUBS-001_REPORT.md` — what stubs return
- `tests/unit/test_phases_stub.py` — how stubs are called (LLMClient = None)

## Context

Part A (infrastructure) and B.0a/B.0b are complete. We have:
- Phase stubs in `src/phases/` returning hardcoded data
- Storage module for loading/saving simulations
- `demo-sim` with 2 characters and 2 locations
- Specifications for Runner, CLI, Narrators (all NOT_STARTED)

**Goal:** Assemble the skeleton — implement Runner, CLI, and Narrators so that:
```bash
python -m src.cli run demo-sim
# Outputs hardcoded narrative to console
# simulation.json: current_tick 0 → 1
```

## Key Design Decisions

### Path Resolution
Runner resolves simulation path as:
```python
sim_path = config._project_root / "simulations" / sim_id
```
No additional path configuration needed. Convention: all simulations live in `simulations/` folder.

### LLMClient in Skeleton
Phase stubs ignore `llm_client` parameter. For skeleton, pass `None`:
```python
result = await execute_phase1(simulation, config, None)  # type: ignore[arg-type]
```
Real LLMClient will be created when implementing B.1b (Phase 1 with actual LLM).

### ConsoleNarrator Empty Narratives
Output ALL locations. If narrative is empty, mark it visibly (e.g., `[No narrative]`). Exact format is implementation choice — we'll adjust later if needed.

## Steps

### 1. Create `src/runner.py`

Implement according to `docs/specs/core_runner.md`:

**Exceptions:**
- `SimulationBusyError` — raised when simulation status is "running"
- `PhaseError` — raised when any phase fails (wraps phase error)

**TickResult dataclass:**
```python
@dataclass
class TickResult:
    sim_id: str
    tick_number: int              # completed tick number
    narratives: dict[str, str]    # location_id → narrative text
    success: bool
    error: str | None = None
```

**TickRunner class:**
- `__init__(config: Config, narrators: list[Narrator])` — store config and narrators
- `async run_tick(sim_id: str) -> TickResult` — execute one complete tick

**run_tick flow:**
1. Resolve path: `config._project_root / "simulations" / sim_id`
2. Load simulation via `load_simulation(path)`
3. Check status == "paused", raise `SimulationBusyError` if "running"
4. Set status = "running" (in memory)
5. Execute phases sequentially (pass `None` as llm_client):
   - Phase 1: `execute_phase1(simulation, config, None)`
   - Phase 2a: `execute_phase2a(simulation, config, None)`
   - Phase 2b: `execute_phase2b(simulation, config, None)`
   - Phase 3: `execute_phase3(simulation, config, None)`
   - Phase 4: `execute_phase4(simulation, config, None)`
6. If any phase returns `success=False`, raise `PhaseError` with phase name and error
7. Extract narratives from phase2b result: `{loc_id: data[loc_id]["narrative"]}`
8. Increment `simulation.current_tick`
9. Set status = "paused"
10. Save via `save_simulation(path, simulation)`
11. Build `TickResult`
12. Call each narrator with result (catch and log narrator exceptions)
13. Return `TickResult`

**Error handling:**
- `SimulationNotFoundError` from Storage — let propagate
- `StorageIOError` from Storage — let propagate
- Phase failures — wrap in `PhaseError`
- Narrator failures — log warning, continue to next narrator

### 2. Create `src/narrators.py`

Implement according to `docs/specs/core_narrators.md`:

**Narrator Protocol:**
```python
from typing import Protocol

class Narrator(Protocol):
    def output(self, result: TickResult) -> None: ...
```

**ConsoleNarrator:**
- `__init__()` — no configuration
- `output(result: TickResult)` — print to stdout

**Output format:**
```
═══════════════════════════════════════════
TICK 42
═══════════════════════════════════════════

--- Location Name ---
Narrative text here...

--- Another Location ---
[No narrative]

═══════════════════════════════════════════
```

- Use box-drawing character `═` (U+2550) for header/footer
- Separator line between locations: `--- Location Name ---`
- Empty narrative: show location with marker like `[No narrative]`
- Empty line between locations for readability

### 3. Create `src/cli.py`

Implement according to `docs/specs/core_cli.md`:

**Typer application:**
```python
import typer
app = typer.Typer(name="thing-sandbox", help="Thing' Sandbox - LLM-driven text simulation")
```

**Command `run`:**
```bash
python -m src.cli run <sim-id>
```
- Load Config
- Create ConsoleNarrator
- Create TickRunner
- Call `asyncio.run(runner.run_tick(sim_id))`
- Print status message: `[sim-id] Tick N completed.`
- Handle exceptions → appropriate exit codes

**Command `status`:**
```bash
python -m src.cli status <sim-id>
```
- Load Config
- Resolve path, load simulation
- Print: `sim-id: tick N, M characters, K locations, status: STATUS`
- Handle `SimulationNotFoundError` → exit code 2

**Exception → Exit Code mapping:**
| Exception | Exit Code | Message |
|-----------|-----------|---------|
| `ConfigError` | EXIT_CONFIG_ERROR (1) | "Configuration error: {details}" |
| `SimulationNotFoundError` | EXIT_INPUT_ERROR (2) | "Simulation '{id}' not found" |
| `InvalidDataError` | EXIT_INPUT_ERROR (2) | "Invalid simulation data: {details}" |
| `SimulationBusyError` | EXIT_RUNTIME_ERROR (3) | "Simulation '{id}' is busy (status: running)" |
| `PhaseError` | EXIT_RUNTIME_ERROR (3) | "Phase failed: {details}" |
| `StorageIOError` | EXIT_IO_ERROR (5) | "Storage error: {details}" |

**Entry point in `__main__`:**
```python
if __name__ == "__main__":
    app()
```

### 4. Create `tests/integration/test_skeleton.py`

**Test: `test_run_tick_increments_current_tick`**
- Load demo-sim initial state (current_tick should be 0)
- Run tick via TickRunner
- Reload simulation from disk
- Assert current_tick == 1
- Assert status == "paused"

**Test: `test_run_tick_returns_narratives`**
- Run tick on demo-sim
- Assert result.success is True
- Assert result.narratives has entries for all locations
- Assert each narrative is non-empty string (stubs return "[Stub] ...")

**Test: `test_run_tick_simulation_not_found`**
- Try to run tick on "nonexistent-sim"
- Assert raises `SimulationNotFoundError`

**Test: `test_status_command_output`** (optional, CLI test)
- Use `typer.testing.CliRunner`
- Invoke `status demo-sim`
- Assert output contains "demo-sim", "tick", "characters", "locations"

**Fixture considerations:**
- Tests modify demo-sim state — need to reset after each test
- Option A: Copy demo-sim to temp folder, run tests there
- Option B: Save original state, restore in teardown
- Recommend Option A for isolation

### 5. Update spec statuses

After implementation, update status in:
- `docs/specs/core_runner.md`: NOT_STARTED → READY
- `docs/specs/core_cli.md`: NOT_STARTED → READY
- `docs/specs/core_narrators.md`: NOT_STARTED → READY

## Testing

### Quality Checks (run in order)
```bash
cd /path/to/thing-sandbox
source venv/bin/activate  # or appropriate activation for your OS

# Linting
ruff check src/runner.py src/cli.py src/narrators.py tests/integration/test_skeleton.py

# Formatting
ruff format src/runner.py src/cli.py src/narrators.py tests/integration/test_skeleton.py

# Type checking
mypy src/runner.py src/cli.py src/narrators.py

# Unit tests (existing should still pass)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/test_skeleton.py -v
```

### Manual Verification
```bash
# Check demo-sim initial state
cat simulations/demo-sim/simulation.json
# Should show current_tick: 0

# Run one tick
python -m src.cli run demo-sim
# Should output narrative to console

# Check state changed
cat simulations/demo-sim/simulation.json
# Should show current_tick: 1

# Check status command
python -m src.cli status demo-sim
# Should output: demo-sim: tick 1, 2 characters, 2 locations, status: paused

# Test error handling
python -m src.cli run nonexistent-sim
echo $?  # Should be 2 (EXIT_INPUT_ERROR)
```

**Important:** After manual testing, reset demo-sim to tick 0 for future tests:
```bash
# Edit simulations/demo-sim/simulation.json, set current_tick: 0
```

## Deliverables

- [ ] `src/runner.py` — TickRunner implementation
- [ ] `src/narrators.py` — Narrator protocol + ConsoleNarrator
- [ ] `src/cli.py` — Typer CLI with `run` and `status` commands
- [ ] `tests/integration/test_skeleton.py` — E2E tests
- [ ] Specs updated to READY status
- [ ] All quality checks pass
- [ ] Report: `docs/tasks/TS-B.0c-RUNNER-001_REPORT.md`
