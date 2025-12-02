# core_cli.md

## Status: NOT_STARTED

Command-line interface for Thing' Sandbox. Entry point for running simulations
and checking their status.

---

## Public API

### CLI Application

Typer-based CLI application.

```python
app = typer.Typer(
    name="thing-sandbox",
    help="Thing' Sandbox - LLM-driven text simulation"
)
```

### Commands

#### run

Run simulation tick(s).

```bash
python -m src.cli run <sim-id> [OPTIONS]
```

**Arguments:**
- `sim-id` (str, required) — simulation identifier

**Options (MVP):**
- None (runs single tick using config defaults)

**Options (Future):**
- `--continuous` — run in continuous mode (override config)
- `--single` — run single tick (override config)
- `--interval SECONDS` — interval between ticks (override config)
- `--ticks N` — maximum ticks to run (override config)

**Behavior:**
1. Load configuration
2. Resolve run parameters (CLI overrides → config defaults)
3. Execute tick(s) via TickRunner
4. Exit with appropriate code

**MVP Implementation:**
- Ignores config defaults for mode/interval/ticks
- Always runs exactly one tick
- Future options documented but not implemented

#### status

Show simulation status.

```bash
python -m src.cli status <sim-id>
```

**Arguments:**
- `sim-id` (str, required) — simulation identifier

**Output Format:**
```
<sim-id>: tick <N>, <M> characters, <K> locations, status: <status>
```

**Example:**
```
my-sim: tick 42, 3 characters, 2 locations, status: paused
```

**Exit Codes:**
- EXIT_SUCCESS (0) — status displayed
- EXIT_INPUT_ERROR (2) — simulation not found

---

## CLI Options Resolution (Future)

When continuous mode is implemented, options resolve as:

| Config default_mode | CLI flags | Result |
|---------------------|-----------|--------|
| "single" | (none) | single tick |
| "single" | --continuous | continuous mode |
| "continuous" | (none) | continuous mode |
| "continuous" | --single | single tick |

**Interval resolution:**
- CLI `--interval` overrides config `default_interval`
- Only used in continuous mode

**Ticks limit resolution:**
- CLI `--ticks` overrides config `default_ticks_limit`
- 0 = unlimited (only in continuous mode)

---

## Exit Codes

Uses standard codes from `utils/exit_codes.py`:

| Code | Constant | When |
|------|----------|------|
| 0 | EXIT_SUCCESS | Tick(s) completed successfully |
| 1 | EXIT_CONFIG_ERROR | Missing config.toml, invalid config, missing API key |
| 2 | EXIT_INPUT_ERROR | Simulation not found, invalid simulation data |
| 3 | EXIT_RUNTIME_ERROR | Phase failed, LLM returned invalid response |
| 4 | EXIT_API_LIMIT_ERROR | OpenAI rate limit exceeded |
| 5 | EXIT_IO_ERROR | Failed to write simulation state |

---

## Terminal Output

### Run Command

**Success:**
```
[my-sim] Starting tick 43...
[my-sim] Tick 43 completed.
```

**Error:**
```
[my-sim] Error: Phase 1 failed - LLM timeout
```

### Status Command

**Success:**
```
my-sim: tick 42, 3 characters, 2 locations, status: paused
```

**Error:**
```
Error: Simulation 'unknown-sim' not found
```

---

## Error Handling

### Exception Mapping

| Exception | Exit Code | Message |
|-----------|-----------|---------|
| ConfigError | EXIT_CONFIG_ERROR | "Configuration error: {details}" |
| SimulationNotFoundError | EXIT_INPUT_ERROR | "Simulation '{id}' not found" |
| ValidationError | EXIT_INPUT_ERROR | "Invalid simulation data: {details}" |
| PhaseError | EXIT_RUNTIME_ERROR | "Phase {N} failed: {details}" |
| LLMRateLimitError | EXIT_API_LIMIT_ERROR | "Rate limit exceeded, retry later" |
| StorageError | EXIT_IO_ERROR | "Failed to save: {details}" |

### Graceful Shutdown (Future)

In continuous mode, handle SIGINT/SIGTERM:
1. Complete current tick
2. Save state
3. Exit with EXIT_SUCCESS

---

## Dependencies

- **Standard Library**: sys, asyncio
- **External**: typer>=0.9.0
- **Internal**:
  - config (Config, ConfigError)
  - runner (TickRunner, TickResult)
  - utils.storage (Storage, SimulationNotFoundError)
  - utils.exit_codes
  - narrators (ConsoleNarrator)

---

## Usage Examples

### Running Simulation

```bash
# Run single tick (MVP)
python -m src.cli run my-sim

# Future: continuous mode
python -m src.cli run my-sim --continuous

# Future: run 10 ticks with 5 minute interval
python -m src.cli run my-sim --continuous --ticks 10 --interval 300
```

### Checking Status

```bash
python -m src.cli status my-sim
# Output: my-sim: tick 42, 3 characters, 2 locations, status: paused
```

### Scripting Multiple Ticks (MVP workaround)

```bash
# Run 5 ticks
for i in {1..5}; do
    python -m src.cli run my-sim || exit $?
done
```

---

## Test Coverage

### Unit Tests

- test_run_command_success — tick completes, exit 0
- test_run_command_simulation_not_found — exit 2
- test_run_command_config_error — exit 1
- test_run_command_phase_error — exit 3
- test_status_command_success — correct format output
- test_status_command_not_found — exit 2

### Integration Tests

- test_cli_run_full_tick — end-to-end with stubs
- test_cli_status_after_run — status reflects tick increment

---

## Implementation Notes

### Typer Setup

```python
import typer
from src.config import Config
from src.runner import TickRunner

app = typer.Typer()

@app.command()
def run(sim_id: str) -> None:
    """Run simulation tick."""
    ...

@app.command()
def status(sim_id: str) -> None:
    """Show simulation status."""
    ...

if __name__ == "__main__":
    app()
```

### Async in Typer

TickRunner is async, but Typer commands are sync. Use:

```python
import asyncio

@app.command()
def run(sim_id: str) -> None:
    asyncio.run(_run_async(sim_id))

async def _run_async(sim_id: str) -> None:
    runner = TickRunner(...)
    await runner.run_tick(sim_id)
```

### Entry Point

Package entry point in `pyproject.toml`:

```toml
[project.scripts]
thing-sandbox = "src.cli:app"
```

Allows running as:
```bash
thing-sandbox run my-sim
# or
python -m src.cli run my-sim
```
