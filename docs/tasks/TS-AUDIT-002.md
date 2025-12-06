# TS-AUDIT-002: Specs and Tests for Uncovered Modules

## References
- `docs/Thing' Sandbox Specs Writing Guide.md` — for spec format
- `docs/specs/phase_1.md` — example phase spec
- `docs/specs/util_llm_adapter_openai.md` — example adapter spec
- Existing test files in `tests/unit/` for patterns

## Context
Audit AUDIT-001 found modules without specs and unit tests. 
This task covers non-stub modules that are already in use.

**Scope:**
- 2 specs: `phases/common.py`, `utils/llm_adapters/base.py`
- 4 unit tests: `runner.py`, `narrators.py`, `phases/common.py`, `utils/llm_adapters/base.py`

*Phases 2a/2b/4 are stubs — skip them until implementation.*

## Steps

### Part A: Specifications (2 files)

1. **phases/common.py** → `docs/specs/phase_common.md`
   - Read the module, understand PhaseResult and any shared utilities
   - Write spec following the guide

2. **utils/llm_adapters/base.py** → `docs/specs/util_llm_adapter_base.md`
   - Read the module, understand abstract interface
   - Write spec following the guide

### Part B: Unit Tests (4 files)

3. **runner.py** → `tests/unit/test_runner.py`
   - Read `docs/specs/core_runner.md` first
   - Test orchestration logic, phase calling, error handling
   - Mock phases and storage

4. **narrators.py** → `tests/unit/test_narrators.py`
   - Read `docs/specs/core_narrators.md` first  
   - Test each narrator type (console, file, telegram stub)
   - Mock I/O operations

5. **phases/common.py** → `tests/unit/test_phases_common.py`
   - Test PhaseResult creation, success/failure states
   - Test any utility functions

6. **utils/llm_adapters/base.py** → `tests/unit/test_llm_adapter_base.py`
   - Test abstract interface contracts
   - Test data classes (AdapterResponse, etc.)

## Testing
After writing tests:
```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
python -m pytest tests/unit/ -v
```

All tests must pass.

## Deliverables
- `docs/specs/phase_common.md`
- `docs/specs/util_llm_adapter_base.md`
- `tests/unit/test_runner.py`
- `tests/unit/test_narrators.py`
- `tests/unit/test_phases_common.py`
- `tests/unit/test_llm_adapter_base.py`
- `docs/tasks/TS-AUDIT-002_REPORT.md`
