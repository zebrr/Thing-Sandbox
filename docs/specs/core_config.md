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

### Config Attributes

#### Config.simulation: SimulationConfig

Simulation-related settings.

- **memory_cells** (int, 1-10, default=5) — number of memory cells per character

#### Config.openai_api_key: str | None

OpenAI API key from `.env`. None if not set.

#### Config.telegram_bot_token: str | None

Telegram bot token from `.env`. None if not set.

---

## Internal Models

### SimulationConfig

```python
class SimulationConfig(BaseModel):
    memory_cells: int = Field(ge=1, le=10, default=5)
```

### LLMConfig (placeholder for A.5)

```python
class LLMConfig(BaseModel):
    # Will be populated in A.5
    pass
```

---

## Configuration Files

### config.toml

Located in project root. Required.

```toml
[simulation]
memory_cells = 5

[llm]
# Parameters added in A.5
```

### .env

Located in project root. Optional but recommended.

```
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
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

Example:
```
Config error: simulation.memory_cells must be between 1 and 10, got 15
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
import sys

try:
    config = Config.load()
except ConfigError as e:
    print(f"Configuration error: {e}", file=sys.stderr)
    sys.exit(EXIT_CONFIG_ERROR)

try:
    prompt = config.resolve_prompt("unknown_prompt")
except PromptNotFoundError as e:
    print(f"Prompt not found: {e}", file=sys.stderr)
    sys.exit(EXIT_INPUT_ERROR)
```

---

## Test Coverage

- **test_config.py**
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
