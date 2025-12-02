# TS-B.0a-CONFIG-001: Extend SimulationConfig with run parameters

## References

- Specification: `docs/specs/core_config.md` (status: IN_PROGRESS)
- Current implementation: `src/config.py`
- Current config: `config.toml`
- Current tests: `tests/unit/test_config.py`

## Context

B.0a stage requires extending SimulationConfig with new fields for run mode configuration.
These fields will be used by CLI in future phases (B.0c and later) to control tick execution.

Current SimulationConfig has only `memory_cells`. Need to add:
- `default_mode` — "single" or "continuous"
- `default_interval` — seconds between ticks
- `default_ticks_limit` — max ticks (0 = unlimited)

## Steps

### 1. Update src/config.py

Extend `SimulationConfig` class:

```python
class SimulationConfig(BaseModel):
    """Simulation-related configuration settings."""

    memory_cells: int = Field(ge=1, le=10, default=5)
    default_mode: Literal["single", "continuous"] = "single"
    default_interval: int = Field(ge=1, default=600)  # seconds
    default_ticks_limit: int = Field(ge=0, default=0)  # 0 = unlimited
```

Add `Literal` import if not present:
```python
from typing import Literal
```

### 2. Update config.toml

Add new parameters to `[simulation]` section:

```toml
[simulation]
memory_cells = 5
default_mode = "single"
default_interval = 600
default_ticks_limit = 0
```

### 3. Update tests/unit/test_config.py

Add new test cases:

```python
def test_simulation_config_default_mode_single():
    """Test default_mode='single' loads correctly."""
    # Create config with default_mode = "single"
    # Assert config.simulation.default_mode == "single"

def test_simulation_config_default_mode_continuous():
    """Test default_mode='continuous' loads correctly."""
    # Create config with default_mode = "continuous"
    # Assert config.simulation.default_mode == "continuous"

def test_simulation_config_default_mode_invalid():
    """Test invalid default_mode raises ConfigError."""
    # Create config with default_mode = "invalid"
    # Assert raises ConfigError

def test_simulation_config_default_interval_valid():
    """Test default_interval >= 1 loads correctly."""
    # Create config with default_interval = 300
    # Assert config.simulation.default_interval == 300

def test_simulation_config_default_interval_invalid():
    """Test default_interval < 1 raises ConfigError."""
    # Create config with default_interval = 0
    # Assert raises ConfigError

def test_simulation_config_default_ticks_limit_zero():
    """Test default_ticks_limit = 0 means unlimited."""
    # Create config with default_ticks_limit = 0
    # Assert config.simulation.default_ticks_limit == 0

def test_simulation_config_default_ticks_limit_positive():
    """Test positive default_ticks_limit loads correctly."""
    # Create config with default_ticks_limit = 10
    # Assert config.simulation.default_ticks_limit == 10
```

### 4. Update specification status

Change status in `docs/specs/core_config.md`:
```
## Status: READY
```

## Testing

Activate virtual environment before running commands.

```bash
# Quality checks
ruff check src/config.py tests/unit/test_config.py
ruff format src/config.py tests/unit/test_config.py
mypy src/config.py

# Run tests
pytest tests/unit/test_config.py -v

# Expected: all tests pass, including new ones
```

## Deliverables

1. Updated `src/config.py` with extended SimulationConfig
2. Updated `config.toml` with new simulation parameters
3. Updated `tests/unit/test_config.py` with 7 new test cases
4. Updated `docs/specs/core_config.md` status → READY
5. Report: `docs/tasks/TS-B.0a-CONFIG-001_REPORT.md`
