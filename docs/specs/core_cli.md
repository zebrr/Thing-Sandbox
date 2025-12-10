# core_cli.md

## Status: READY

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

**Usage:**
```bash
python -m src.cli [OPTIONS] COMMAND [ARGS]
```

**Options:**
- `--verbose / -v` — Enable DEBUG level logging (default: INFO)

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
2. Load simulation via load_simulation()
3. Resolve output configuration via config.resolve_output(simulation)
4. Create narrators with resolved output config
5. Execute tick(s) via TickRunner
6. Exit with appropriate code

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

#### reset

Reset simulation to template state.

```bash
python -m src.cli reset <sim-id>
```

**Arguments:**
- `sim-id` (str, required) — simulation identifier

**Behavior:**
1. Load configuration
2. Call reset_simulation(sim_id, project_root)
3. Output success message or error

**Output Format:**
```
[sim-id] Reset to template.
```

**Error Output:**
```
Error: Template for 'sim-id' not found
```

**Exit Codes:**
- EXIT_SUCCESS (0) — reset completed
- EXIT_INPUT_ERROR (2) — template not found
- EXIT_IO_ERROR (5) — copy operation failed

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
| TemplateNotFoundError | EXIT_INPUT_ERROR | "Template for '{id}' not found" |
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

- **Standard Library**: sys, asyncio, logging
- **External**: typer>=0.9.0
- **Internal**:
  - config (Config, ConfigError)
  - runner (TickRunner, TickResult)
  - utils.storage (Storage, SimulationNotFoundError)
  - utils.exit_codes
  - utils.logging_config (setup_logging)
  - narrators (ConsoleNarrator, TelegramNarrator)
  - utils.telegram_client (TelegramClient)

---

## Usage Examples

### Running Simulation

```bash
# Run single tick (MVP)
python -m src.cli run my-sim

# Run with verbose logging
python -m src.cli --verbose run my-sim

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
- test_reset_command_success — reset completes, exit 0
- test_reset_command_template_not_found — exit 2
- test_reset_command_storage_error — exit 5
- test_cli_creates_telegram_narrator — TelegramNarrator created when enabled with token
- test_cli_warns_no_token — warning when enabled but no token
- test_cli_telegram_disabled — no TelegramNarrator when disabled
- test_cli_telegram_mode_none — no TelegramNarrator when mode="none"

### Integration Tests

- test_cli_run_full_tick — end-to-end with stubs
- test_cli_status_after_run — status reflects tick increment

---

## Implementation Notes

### Typer Setup

```python
import logging
import typer
from src.config import Config
from src.runner import TickRunner
from src.utils.logging_config import setup_logging

app = typer.Typer()

@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Thing' Sandbox CLI - LLM-driven text simulation."""
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(level=level)

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
from src.utils.storage import load_simulation

@app.command()
def run(sim_id: str) -> None:
    config = Config.load()
    sim_path = config.project_root / "simulations" / sim_id
    simulation = load_simulation(sim_path)
    output_config = config.resolve_output(simulation)
    asyncio.run(_run_tick(config, simulation, sim_path, output_config))

async def _run_tick(config, simulation, sim_path, output_config) -> None:
    narrators = [ConsoleNarrator(show_narratives=output_config.console.show_narratives)]

    # Telegram narrator (if enabled and mode != none)
    if output_config.telegram.enabled and output_config.telegram.mode != "none":
        if not config.telegram_bot_token:
            typer.echo("Telegram enabled but TELEGRAM_BOT_TOKEN not set", err=True)
        else:
            client = TelegramClient(config.telegram_bot_token)
            narrators.append(TelegramNarrator(
                client=client,
                chat_id=output_config.telegram.chat_id,
                mode=output_config.telegram.mode,
                group_intentions=output_config.telegram.group_intentions,
                group_narratives=output_config.telegram.group_narratives,
            ))

    runner = TickRunner(config, narrators)
    await runner.run_tick(simulation, sim_path)
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
