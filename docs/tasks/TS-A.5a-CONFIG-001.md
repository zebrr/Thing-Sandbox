# TS-A.5a-CONFIG-001: Extend Config with Phase Configuration

## References

Read before starting:
- `docs/specs/core_config.md` — updated specification (this task implements it)
- `docs/Thing' Sandbox LLM Approach v2.md` — section 11 (Configuration)

## Context

Config module (A.3) currently loads only `[simulation]` section. We need to extend it
to load LLM phase configurations: `[phase1]`, `[phase2a]`, `[phase2b]`, `[phase4]`.

Each phase has identical structure (PhaseConfig) but different values. These configs
will be used by OpenAI Adapter in A.5b.

**Current state:**
- `src/config.py` has placeholder `LLMConfig` class (empty)
- `config.toml` has only `[simulation]` section

**Goal:**
- Add `PhaseConfig` Pydantic model with validation
- Load all four phase sections into Config
- Update config.toml with phase sections
- Full test coverage for new functionality

## Steps

### 1. Update `src/config.py`

Add PhaseConfig model:

```python
from typing import Literal

class PhaseConfig(BaseModel):
    """Configuration for a single LLM phase."""
    
    model: str  # Required, no default
    is_reasoning: bool = False
    max_context_tokens: int = Field(ge=1, default=128000)
    max_completion: int = Field(ge=1, default=4096)
    timeout: int = Field(ge=1, default=600)
    max_retries: int = Field(ge=0, le=10, default=3)
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    reasoning_summary: Literal["auto", "concise", "detailed"] | None = None
    verbosity: Literal["low", "medium", "high"] | None = None
    truncation: Literal["auto", "disabled"] | None = None
    response_chain_depth: int = Field(ge=0, default=0)
```

Update Config class:
- Remove `LLMConfig` placeholder
- Add attributes: `phase1`, `phase2a`, `phase2b`, `phase4` (all PhaseConfig)
- Update `__init__` to accept phase configs
- Update `load()` to parse all phase sections
- Raise `ConfigError` if any phase section is missing

### 2. Update `config.toml`

Add all four phase sections with values from LLM Approach v2.md section 11:

```toml
[phase1]
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
```

### 3. Update `tests/unit/test_config.py`

Add new test cases:

```python
def test_phase_config_loading():
    """All phase configs loaded correctly."""
    config = Config.load()
    assert config.phase1.model == "gpt-5-mini-2025-08-07"
    assert config.phase2a.response_chain_depth == 2
    assert config.phase2b.timeout == 600
    assert config.phase4.is_reasoning is True

def test_phase_config_defaults():
    """Default values applied when not specified in TOML."""
    # Create minimal config with only required 'model' field
    # Verify defaults are applied

def test_phase_config_model_required():
    """Missing model field raises ConfigError."""
    # Create config without model in phase1
    # Verify ConfigError raised

def test_phase_config_invalid_reasoning_effort():
    """Invalid reasoning_effort value raises ConfigError."""
    # Set reasoning_effort = "extreme"
    # Verify ConfigError with clear message

def test_phase_config_invalid_timeout():
    """Timeout < 1 raises ConfigError."""
    # Set timeout = 0
    # Verify ConfigError

def test_phase_config_optional_none():
    """Omitted optional fields result in None."""
    # Load config without verbosity set
    # Verify config.phase1.verbosity is None

def test_phase_config_missing_section():
    """Missing phase section raises ConfigError."""
    # Create config without [phase2a]
    # Verify ConfigError mentions missing section
```

Use tmp_path fixture to create test config files.

## Testing

```bash
# Activate venv first!
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Quality checks
ruff check src/config.py tests/unit/test_config.py
ruff format src/config.py tests/unit/test_config.py
mypy src/config.py

# Run tests
pytest tests/unit/test_config.py -v

# Expected: all tests pass, no linting errors
```

## Deliverables

1. **Updated module:** `src/config.py`
   - PhaseConfig model with validation
   - Config.phase1, phase2a, phase2b, phase4 attributes
   - LLMConfig placeholder removed
   
2. **Updated config:** `config.toml`
   - Four phase sections with values from LLM Approach v2.md
   
3. **Updated tests:** `tests/unit/test_config.py`
   - 7+ new test cases for PhaseConfig
   - All existing tests still pass
   
4. **Report:** `docs/tasks/TS-A.5a-CONFIG-001_REPORT.md`
