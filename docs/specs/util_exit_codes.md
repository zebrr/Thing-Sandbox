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

### Unit Tests (tests/unit/test_exit_codes.py)

**TestExitCodeConstants:**
- test_exit_success_is_zero
- test_exit_config_error_is_one
- test_exit_input_error_is_two
- test_exit_runtime_error_is_three
- test_exit_api_limit_error_is_four
- test_exit_io_error_is_five

**TestExitCodeDictionaries:**
- test_all_codes_have_names
- test_all_codes_have_descriptions

**TestGetExitCodeName:**
- test_returns_success_for_zero
- test_returns_config_error_for_one
- test_returns_input_error_for_two
- test_returns_runtime_error_for_three
- test_returns_api_limit_error_for_four
- test_returns_io_error_for_five
- test_returns_unknown_for_unknown_code
- test_returns_unknown_for_negative_code

**TestGetExitCodeDescription:**
- test_returns_description_for_success
- test_returns_description_for_config_error
- test_returns_description_for_input_error
- test_returns_description_for_runtime_error
- test_returns_description_for_api_limit_error
- test_returns_description_for_io_error
- test_returns_unknown_description_for_unknown_code
- test_returns_unknown_description_for_negative_code

**TestLogExit:**
- test_success_logs_via_info
- test_config_error_logs_via_error
- test_input_error_logs_via_error
- test_runtime_error_logs_via_error
- test_api_limit_error_logs_via_error
- test_io_error_logs_via_error
- test_log_message_includes_code_name
- test_log_message_includes_description
- test_log_message_includes_custom_message
- test_log_message_without_custom_message
- test_unknown_code_logs_via_error

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
