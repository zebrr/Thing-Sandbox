# util_exit_codes.md

## Status: READY

Standard exit codes for CLI. Provides consistent error handling through a unified code system with support for readable names and logging.

## Public API

### Constants

#### Exit Codes
- **EXIT_SUCCESS** = 0 - Successful execution
- **EXIT_CONFIG_ERROR** = 1 - Configuration errors (missing API key, broken config.toml)
- **EXIT_INPUT_ERROR** = 2 - Input data errors (broken character/location JSON, invalid schemas)
- **EXIT_RUNTIME_ERROR** = 3 - Runtime errors (LLM failures after retries, unexpected exceptions)
- **EXIT_API_LIMIT_ERROR** = 4 - Rate limits (OpenAI TPM/RPM limits)
- **EXIT_IO_ERROR** = 5 - File system errors (cannot write to simulations/)

#### Dictionaries
- **EXIT_CODE_NAMES** - Dictionary {code: name} for logging
- **EXIT_CODE_DESCRIPTIONS** - Dictionary {code: description} for documentation

### Functions

#### get_exit_code_name(code: int) -> str
Returns readable name for exit code.
- **Input**: code - exit code integer
- **Returns**: code name (e.g. "CONFIG_ERROR") or "UNKNOWN({code})" for unknown codes

#### get_exit_code_description(code: int) -> str
Returns description for exit code.
- **Input**: code - exit code integer
- **Returns**: code description or "Unknown exit code: {code}"

#### log_exit(logger: logging.Logger, code: int, message: str = None) -> None
Logs exit code with optional message.
- **Input**: 
  - logger - logger object
  - code - exit code
  - message - additional context (optional)
- **Behavior**: 
  - SUCCESS logged via logger.info()
  - All other codes via logger.error()
  - Includes code name and description

## Error Code Guidelines

**Codes 1-2**: User-fixable problems
- CONFIG_ERROR: check config.toml, API keys, .env file
- INPUT_ERROR: check simulation files, character/location JSON, schemas

**Code 3**: Runtime errors requiring investigation
- RUNTIME_ERROR: LLM returned invalid response after all retries, unexpected exceptions

**Code 4**: Temporary API limitations
- API_LIMIT_ERROR: wait and retry later

**Code 5**: Filesystem problems
- IO_ERROR: check permissions, disk space, path validity

## Dependencies

- **Standard Library**: logging
- **External**: None
- **Internal**: None

## Test Coverage

TBD

## Usage Examples

### Basic usage in CLI
```python
from src.utils.exit_codes import EXIT_SUCCESS, EXIT_CONFIG_ERROR, EXIT_INPUT_ERROR
import sys

def main():
    if not config.api_key:
        print("Error: OPENAI_API_KEY not found", file=sys.stderr)
        sys.exit(EXIT_CONFIG_ERROR)
    
    if not simulation_path.exists():
        print(f"Error: Simulation not found: {simulation_path}", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    
    # ... run simulation ...
    sys.exit(EXIT_SUCCESS)
```

### Usage with logging
```python
from src.utils.exit_codes import EXIT_SUCCESS, EXIT_RUNTIME_ERROR, log_exit
import logging

logger = logging.getLogger(__name__)

try:
    run_tick(simulation)
    log_exit(logger, EXIT_SUCCESS, f"Tick {tick} completed")
    sys.exit(EXIT_SUCCESS)
except Exception as e:
    log_exit(logger, EXIT_RUNTIME_ERROR, f"Tick failed: {e}")
    sys.exit(EXIT_RUNTIME_ERROR)
```

### Runner error handling pattern
```python
from src.utils.exit_codes import (
    EXIT_SUCCESS, EXIT_CONFIG_ERROR, EXIT_INPUT_ERROR,
    EXIT_RUNTIME_ERROR, EXIT_API_LIMIT_ERROR, EXIT_IO_ERROR
)

def run() -> int:
    try:
        # Load and validate
        config = load_config()  # may raise ConfigError
        simulation = load_simulation(path)  # may raise InputError
        
        # Execute tick
        run_tick(simulation)  # may raise RuntimeError, APILimitError
        
        # Save results
        save_simulation(simulation)  # may raise IOError
        
        return EXIT_SUCCESS
        
    except ConfigError:
        return EXIT_CONFIG_ERROR
    except InputError:
        return EXIT_INPUT_ERROR
    except APILimitError:
        return EXIT_API_LIMIT_ERROR
    except IOError:
        return EXIT_IO_ERROR
    except Exception:
        return EXIT_RUNTIME_ERROR
```
