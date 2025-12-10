# core_config.md

## Status: READY

Configuration loader for Thing' Sandbox. Loads application settings from `config.toml` 
and secrets from `.env`, provides prompt resolution with simulation-specific overrides.

---

## Public API

### Config

Main configuration class. Singleton-like usage through `Config.load()`.

#### Config.load(config_path: Path | None = None) -> Config

Loads configuration from files.

- **Input**:
  - config_path — path to `config.toml`, default: project root
- **Returns**: Config instance with all settings loaded
- **Raises**:
  - ConfigError (EXIT_CONFIG_ERROR) — missing config.toml, invalid TOML syntax, validation errors
- **Side effects**: reads `.env` file if present

#### Config.resolve_prompt(prompt_name: str, sim_path: Path | None = None) -> Path

Resolves prompt file path with simulation override support.

- **Input**:
  - prompt_name — prompt identifier without extension (e.g., "phase1_intention")
  - sim_path — path to simulation folder (optional)
- **Returns**: Path to prompt file
- **Raises**:
  - PromptNotFoundError (EXIT_INPUT_ERROR) — default prompt not found
- **Resolution order**:
  1. `{sim_path}/prompts/{prompt_name}.md` (if sim_path provided and file exists)
  2. `src/prompts/{prompt_name}.md` (default)
- **Warnings**: logs warning if sim_path provided but override not found
- **Integration**: used by `PromptRenderer` (see `docs/specs/util_prompts.md`)

#### Config.resolve_output(simulation: Simulation | None = None) -> OutputConfig

Resolves output configuration with simulation-specific overrides.

- **Input**:
  - simulation — Simulation instance (optional)
- **Returns**: OutputConfig with merged settings
- **Behavior**:
  - Starts with values from config.toml
  - If simulation provided and has `output` section in `__pydantic_extra__`, merges those values
  - Merging is done per-channel (console, file, telegram)
  - Simulation values override config.toml values for specific fields
  - **Fallback**: if `telegram.chat_id` is empty after merge, uses `TELEGRAM_TEST_CHAT_ID` from `.env`
  - **Fallback**: if `telegram.message_thread_id` is None after merge, uses `TELEGRAM_TEST_THREAD_ID` from `.env`
- **Example**:
  ```python
  config = Config.load()
  sim = load_simulation(sim_path)
  output_config = config.resolve_output(sim)
  # output_config.telegram.chat_id may be from simulation.json
  ```
- **Simulation JSON override format**:
  ```json
  {
    "id": "my-sim",
    "output": {
      "telegram": {
        "enabled": true,
        "chat_id": "12345",
        "mode": "narratives"
      }
    }
  }
  ```

### Config Attributes

#### Config.simulation: SimulationConfig

Simulation-related settings.

- **memory_cells** (int, 1-10, default=5) — number of memory cells per character
- **default_mode** ("single" | "continuous", default="single") — default run mode
- **default_interval** (int, ≥1, default=600) — seconds between ticks in continuous mode
- **default_ticks_limit** (int, ≥0, default=0) — max ticks to run, 0 = unlimited

#### Config.phase1: PhaseConfig

LLM configuration for Phase 1 (character intentions).

#### Config.phase2a: PhaseConfig

LLM configuration for Phase 2a (game master arbitration).

#### Config.phase2b: PhaseConfig

LLM configuration for Phase 2b (narrative generation).

#### Config.phase4: PhaseConfig

LLM configuration for Phase 4 (memory summarization).

#### Config.openai_api_key: str | None

OpenAI API key from `.env`. None if not set.

#### Config.telegram_bot_token: str | None

Telegram bot token from `.env`. None if not set.

#### Config.telegram_test_chat_id: str | None

Default Telegram chat ID from `.env` (TELEGRAM_TEST_CHAT_ID). Used as fallback in `resolve_output()` when `chat_id` is empty after merging config.toml and simulation.json. None if not set.

#### Config.telegram_test_thread_id: int | None

Default Telegram thread ID from `.env` (TELEGRAM_TEST_THREAD_ID). Used as fallback in `resolve_output()` when `message_thread_id` is None after merging config.toml and simulation.json. None if not set.

#### Config.project_root: Path

Project root directory path. Auto-detected by searching for `pyproject.toml` from current directory upward.

Used for:
- Resolving `simulations/` path
- Resolving default prompts in `src/prompts/`

#### Config.output: OutputConfig

Output channel configuration.

- **console** — ConsoleOutputConfig: console output settings
- **file** — FileOutputConfig: file (TickLogger) output settings
- **telegram** — TelegramOutputConfig: Telegram output settings (future)

---

## Internal Models

### SimulationConfig

```python
class SimulationConfig(BaseModel):
    memory_cells: int = Field(ge=1, le=10, default=5)
    default_mode: Literal["single", "continuous"] = "single"
    default_interval: int = Field(ge=1, default=600)  # seconds
    default_ticks_limit: int = Field(ge=0, default=0)  # 0 = unlimited
```

**Field semantics:**
- `memory_cells` — number of FIFO memory cells per character
- `default_mode` — default run mode ("single" = one tick, "continuous" = loop with interval)
- `default_interval` — seconds between ticks in continuous mode
- `default_ticks_limit` — maximum ticks to run (0 = unlimited)

### PhaseConfig

LLM phase configuration. All phases share the same structure but may have different values.

```python
class PhaseConfig(BaseModel):
    """Configuration for a single LLM phase."""
    
    model: str
    is_reasoning: bool = False
    max_context_tokens: int = Field(ge=1, default=128000)
    max_completion: int = Field(ge=1, default=4096)
    timeout: int = Field(ge=1, default=600)  # seconds
    max_retries: int = Field(ge=0, le=10, default=3)
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    reasoning_summary: Literal["auto", "concise", "detailed"] | None = None
    verbosity: Literal["low", "medium", "high"] | None = None
    truncation: Literal["auto", "disabled"] | None = None
    response_chain_depth: int = Field(ge=0, default=0)
```

**Field semantics:**
- `model` — OpenAI model identifier (required, no default)
- `is_reasoning` — whether model supports reasoning (extended thinking)
- `max_context_tokens` — maximum input context size
- `max_completion` — maximum output tokens (max_output_tokens in API)
- `timeout` — request timeout in seconds (passed to httpx)
- `max_retries` — retry attempts for rate limit / transient errors
- `reasoning_effort` — reasoning intensity (only if is_reasoning=true)
- `reasoning_summary` — reasoning summary mode (only if is_reasoning=true)
- `verbosity` — output verbosity level
- `truncation` — context truncation strategy
- `response_chain_depth` — depth of response chain (0 = independent requests)

**None handling:** Fields with `None` value are not passed to OpenAI API.

### OutputConfig

Output channels configuration. Controls where simulation output is sent.

```python
class OutputConfig(BaseModel):
    console: ConsoleOutputConfig = Field(default_factory=ConsoleOutputConfig)
    file: FileOutputConfig = Field(default_factory=FileOutputConfig)
    telegram: TelegramOutputConfig = Field(default_factory=TelegramOutputConfig)
```

### ConsoleOutputConfig

Console output settings.

```python
class ConsoleOutputConfig(BaseModel):
    show_narratives: bool = True
```

**Field semantics:**
- `show_narratives` — whether to show narrative text (default: True)

### FileOutputConfig

File output (TickLogger) settings.

```python
class FileOutputConfig(BaseModel):
    enabled: bool = True
```

**Field semantics:**
- `enabled` — whether to write tick logs to file

### TelegramOutputConfig

Telegram output settings. These are defaults that can be overridden per-simulation in `simulation.json`.

```python
class TelegramOutputConfig(BaseModel):
    enabled: bool = False
    chat_id: str = ""
    mode: Literal["none", "narratives", "narratives_stats", "full", "full_stats"] = "none"
    group_intentions: bool = True
    group_narratives: bool = True
    message_thread_id: int | None = None
```

**Field semantics:**
- `enabled` — whether to send to Telegram (default: False)
- `chat_id` — Telegram chat ID for notifications (default: "")
- `mode` — output mode determining what to send (default: "none")
  - "none" — no output
  - "narratives" — only narratives
  - "narratives_stats" — narratives with statistics
  - "full" — full output
  - "full_stats" — full output with statistics
- `group_intentions` — whether to group intentions in output (default: True)
- `group_narratives` — whether to group narratives in output (default: True)
- `message_thread_id` — forum topic ID for supergroups with topics enabled (default: None)

---

## Configuration Files

### config.toml

Located in project root. Required.

```toml
[simulation]
memory_cells = 5
default_mode = "single"
default_interval = 600
default_ticks_limit = 0

[phase1]
model = "gpt-5-mini-2025-08-07"
is_reasoning = true
max_context_tokens = 400000
max_completion = 128000
timeout = 600
max_retries = 3
reasoning_effort = "medium"
reasoning_summary = "auto"
# verbosity = "medium"  # Commented = None (not passed to API)
truncation = "auto"
response_chain_depth = 0

[phase2a]
model = "gpt-5.1-2025-11-13"
is_reasoning = true
max_context_tokens = 400000
max_completion = 128000
timeout = 600
max_retries = 3
reasoning_effort = "medium"
reasoning_summary = "auto"
truncation = "auto"
response_chain_depth = 2

[phase2b]
model = "gpt-5-mini-2025-08-07"
is_reasoning = true
max_context_tokens = 400000
max_completion = 128000
timeout = 600
max_retries = 3
reasoning_effort = "medium"
reasoning_summary = "auto"
truncation = "auto"
response_chain_depth = 0

[phase4]
model = "gpt-5-mini-2025-08-07"
is_reasoning = true
max_context_tokens = 400000
max_completion = 128000
timeout = 600
max_retries = 3
reasoning_effort = "medium"
reasoning_summary = "auto"
truncation = "auto"
response_chain_depth = 0

[output.console]
show_narratives = true

[output.file]
enabled = true

[output.telegram]
enabled = false
chat_id = ""
mode = "none"
group_intentions = true
group_narratives = true
# message_thread_id =
```

### .env

Located in project root. Optional but recommended.

```
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_TEST_CHAT_ID=...  # Default chat_id fallback
TELEGRAM_TEST_THREAD_ID=...  # Default message_thread_id fallback (int)
```

---

## Error Handling

### Exit Codes

- **EXIT_CONFIG_ERROR (1)** — config.toml missing, invalid syntax, validation failure
- **EXIT_INPUT_ERROR (2)** — default prompt file not found

### Error Messages

Config errors include:
- File path that failed
- Specific validation error (field name, constraint violated, actual value)

Examples:
```
Config error: simulation.memory_cells must be between 1 and 10, got 15
Config error: phase1.model is required
Config error: phase2a.reasoning_effort must be 'low', 'medium', or 'high', got 'extreme'
```

---

## Dependencies

- **Standard Library**: pathlib, os, logging
- **External**: pydantic>=2.0, pydantic-settings>=2.0, tomli (Python <3.11) or tomllib
- **Internal**: utils.exit_codes

---

## Usage Examples

### Basic Usage

```python
from src.config import Config

config = Config.load()
print(config.simulation.memory_cells)  # 5
print(config.openai_api_key)  # sk-...
```

### Phase Config Access

```python
from src.config import Config

config = Config.load()

# Access phase configurations
print(config.phase1.model)           # "gpt-5-mini-2025-08-07"
print(config.phase1.timeout)         # 600
print(config.phase2a.response_chain_depth)  # 2

# Optional fields
print(config.phase1.reasoning_effort)  # "medium"
print(config.phase1.verbosity)         # None (not set in config)
```

### Prompt Resolution

```python
from pathlib import Path
from src.config import Config

config = Config.load()
sim_path = Path("simulations/my-sim")

# Returns sim override if exists, otherwise default
prompt_path = config.resolve_prompt("phase1_intention", sim_path)

# Without simulation context — always returns default
default_prompt = config.resolve_prompt("phase2_master")
```

### Error Handling

```python
from src.config import Config, ConfigError, PromptNotFoundError
from src.utils.exit_codes import EXIT_CONFIG_ERROR, EXIT_INPUT_ERROR
import typer

try:
    config = Config.load()
except ConfigError as e:
    typer.echo(f"Configuration error: {e}", err=True)
    raise typer.Exit(code=EXIT_CONFIG_ERROR)

try:
    prompt = config.resolve_prompt("unknown_prompt")
except PromptNotFoundError as e:
    typer.echo(f"Prompt not found: {e}", err=True)
    raise typer.Exit(code=EXIT_INPUT_ERROR)
```

---

## Test Coverage

### Existing Tests (from A.3)

- test_load_valid_config — loads config.toml successfully
- test_load_missing_config — raises ConfigError
- test_load_invalid_toml — raises ConfigError  
- test_load_validation_error — invalid values raise ConfigError
- test_env_loading — secrets loaded from .env
- test_env_missing — works without .env, secrets are None
- test_resolve_prompt_default — returns default prompt path
- test_resolve_prompt_override — returns simulation override
- test_resolve_prompt_missing_default — raises PromptNotFoundError
- test_resolve_prompt_missing_override_warning — logs warning, returns default

### New Tests (for A.5a)

- test_phase_config_loading — all phase configs loaded correctly
- test_phase_config_defaults — default values applied when not specified
- test_phase_config_model_required — missing model raises ConfigError
- test_phase_config_invalid_reasoning_effort — invalid enum value raises ConfigError
- test_phase_config_invalid_timeout — timeout < 1 raises ConfigError
- test_phase_config_optional_none — commented fields result in None
- test_phase_config_all_phases_present — phase1, phase2a, phase2b, phase4 all accessible

### New Tests (for B.0a)

- test_simulation_config_default_mode_single — default_mode="single" loads correctly
- test_simulation_config_default_mode_continuous — default_mode="continuous" loads correctly
- test_simulation_config_default_mode_invalid — invalid mode raises ConfigError
- test_simulation_config_default_interval_valid — interval ≥1 loads correctly
- test_simulation_config_default_interval_invalid — interval < 1 raises ConfigError
- test_simulation_config_default_ticks_limit_zero — 0 means unlimited
- test_simulation_config_default_ticks_limit_positive — positive limit loads correctly

### New Tests (for B.5a)

- test_output_config_defaults — OutputConfig has sensible defaults
- test_console_output_config_custom — ConsoleOutputConfig accepts custom values
- test_file_output_config_custom — FileOutputConfig accepts custom values
- test_telegram_output_config_custom — TelegramOutputConfig accepts custom values
- test_output_config_from_toml — output config loaded correctly from config.toml
- test_output_config_missing_uses_defaults — missing [output] section uses defaults
- test_output_config_partial_section — partial output section fills missing with defaults

### New Tests (for REFACTOR-CONFIG-001)

- test_resolve_output_fallback_chat_id — empty chat_id after merge uses telegram_test_chat_id from .env
- test_resolve_output_no_fallback_when_chat_id_set — chat_id in simulation.json not overwritten by fallback
- test_resolve_output_no_fallback_when_default_empty — empty chat_id and empty telegram_test_chat_id remains empty

### New Tests (for TS-TG-TOPICS-001)

- test_message_thread_id_default — message_thread_id defaults to None
- test_message_thread_id_custom — message_thread_id accepts int value
- test_env_loading_with_thread_id — TELEGRAM_TEST_THREAD_ID loaded from .env
- test_output_config_from_toml_with_thread_id — message_thread_id loaded from config.toml
- test_resolve_output_fallback_thread_id — empty message_thread_id uses telegram_test_thread_id from .env
- test_resolve_output_no_fallback_when_thread_id_set — message_thread_id in simulation.json not overwritten
- test_resolve_output_partial_override_thread_id — partial override merges correctly

---

## Implementation Notes

### Pydantic Settings

Use `pydantic-settings` for unified config loading:
- TOML parsing via `tomllib` (Python 3.11+) or `tomli`
- Environment variables via `SettingsConfigDict(env_file='.env')`

### Project Root Detection

Config needs to find project root for:
- `config.toml` location
- `src/prompts/` default prompts path

Options:
- Walk up from `__file__` looking for `pyproject.toml`
- Use environment variable `THING_SANDBOX_ROOT`
- Accept explicit path in `Config.load()`

Recommended: walk up + explicit override for tests.

### Logging

Use standard `logging` module:
- DEBUG: config values loaded (redact secrets)
- WARNING: simulation prompt override not found
- ERROR: validation failures before raising

### PhaseConfig Parsing

Each phase section is parsed independently. Missing section raises ConfigError.
All four phase sections are required in config.toml.
