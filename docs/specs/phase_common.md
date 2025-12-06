# phase_common.md

## Status: READY

Common types shared by all phase modules. Provides `PhaseResult` dataclass
for unified phase execution results.

---

## Public API

### PhaseResult

Dataclass representing the result of phase execution.

```python
@dataclass
class PhaseResult:
    success: bool
    data: Any
    error: str | None = None
```

**Attributes:**
- **success** (bool) — whether the phase completed successfully
- **data** (Any) — phase-specific output data; type depends on phase:
  - Phase 1: `dict[str, IntentionResponse]`
  - Phase 2a: `dict[str, MasterOutput]`
  - Phase 2b: `dict[str, dict]` with "narrative" key
  - Phase 3: `dict` with "pending_memories" key
  - Phase 4: `None`
- **error** (str | None) — error message if success is False, None otherwise

**Usage:**

```python
from src.phases.common import PhaseResult

# Success case
result = PhaseResult(success=True, data={"intentions": {}})
assert result.error is None

# Failure case
result = PhaseResult(success=False, data=None, error="LLM timeout")
assert not result.success
```

---

## Design Decisions

### Why dataclass (not Pydantic)?

- Simple container with no validation logic
- No serialization needed (internal communication only)
- Minimal overhead for high-frequency instantiation

### Why Any for data?

- Each phase returns different data structure
- Avoids complex union types
- Runner accesses data with known types per phase

### Why not frozen?

- PhaseResult is created once and passed through
- No mutation expected, but frozen adds overhead
- Trade-off: simplicity over strict immutability

---

## Dependencies

- **Standard Library**: dataclasses, typing
- **External**: None
- **Internal**: None

---

## Test Coverage

- **test_phases_common.py**: 5 tests
  - test_phase_result_success_with_data
  - test_phase_result_failure_with_error
  - test_phase_result_default_error_is_none
  - test_phase_result_data_accepts_any_type
  - test_phase_result_equality

---

## Usage Examples

### Creating Success Result

```python
from src.phases.common import PhaseResult

# Phase 1 returns intentions
intentions = {"bob": IntentionResponse(intention="go to tavern")}
result = PhaseResult(success=True, data=intentions)

if result.success:
    process_intentions(result.data)
```

### Creating Failure Result

```python
from src.phases.common import PhaseResult

try:
    data = await llm_client.call()
except LLMError as e:
    result = PhaseResult(success=False, data=None, error=str(e))
```

### In Phase Implementation

```python
async def execute_phase1(simulation, config, llm_client) -> PhaseResult:
    try:
        intentions = await gather_intentions(simulation, llm_client)
        return PhaseResult(success=True, data=intentions)
    except Exception as e:
        return PhaseResult(success=False, data=None, error=str(e))
```

### In Runner

```python
result = await execute_phase1(simulation, config, llm_client)
if not result.success:
    raise PhaseError("phase1", result.error or "Unknown error")
```
