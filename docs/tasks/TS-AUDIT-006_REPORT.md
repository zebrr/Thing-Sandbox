# AUDIT-006 Report: Test Consistency

## Summary

Audited test consistency across 5 dimensions. Found and fixed 1 issue: `test_skeleton.py` missing `@pytest.mark.integration` marker.

**Results:**
- Markers: 1 fix applied
- Mocks: Consistent patterns
- tmp_path: Proper usage
- Naming: Good conventions
- Isolation: No issues

---

## 1. Markers Analysis

### Current Usage

| File | pytestmark | @asyncio | @integration | @slow | @timeout |
|------|------------|----------|--------------|-------|----------|
| test_llm_adapter_openai_live.py | ✅ [integration, slow] | Per test | Module | Module | Per test |
| test_llm_integration.py | ✅ [integration, slow] | Per test | Module | Module | Per test |
| test_phase1_integration.py | ✅ [integration, slow] | Per test | Module | Module | Per test |
| test_skeleton.py | ~~❌ missing~~ ✅ FIXED | Per test | ~~❌~~ ✅ | — | — |

### Integration Files Without LLM Calls

`test_skeleton.py` doesn't make real API calls (uses mocks), so `@pytest.mark.slow` is not needed. Only `@pytest.mark.integration` required for proper filtering.

### Issues Found & Fixed

**test_skeleton.py**: Was missing `pytestmark = pytest.mark.integration`

**Before:**
```bash
pytest -m "not integration" --collect-only | grep skeleton
# Found 9 tests (wrong!)
```

**After:**
```bash
pytest -m "not integration" --collect-only | grep skeleton
# No skeleton tests found (correct!)
```

---

## 2. Mocks Analysis

### Patterns Used

| Pattern | Usage | Files |
|---------|-------|-------|
| `unittest.mock.patch` (context manager) | Primary for replacing modules | test_phase1.py, test_cli.py, test_skeleton.py |
| `unittest.mock.MagicMock` | Sync mock objects | test_cli.py, test_phase1.py, test_exit_codes.py |
| `unittest.mock.AsyncMock` | Async mock objects | test_phase1.py (llm_client.create_batch) |
| `pytest.monkeypatch` | Environment/attribute patching | test_skeleton.py, test_config.py |

### Consistency

**Good:**
- `patch()` always patches where imported, not where defined
- `AsyncMock` correctly used for async methods
- `MagicMock` for sync objects

**Pattern split:**
- `monkeypatch` used in integration tests (test_skeleton.py) for `Config.load`
- `patch()` used in unit tests (test_cli.py) for same purpose

This is acceptable — both work correctly.

### Recommendations

None. Current patterns are appropriate.

---

## 3. tmp_path Usage

### Good Practices

| File | Usage |
|------|-------|
| test_skeleton.py | `tmp_path / "simulations"` for isolated simulation copies |
| test_cli.py | `tmp_path / "simulations" / "_templates"` for template tests |
| test_config.py | `tmp_path / "config.toml"` for config file tests |
| test_prompts.py | `tmp_path` for temporary prompt files |
| test_storage.py | `tmp_path` for simulation read/write tests |

### Potential Concern

**test_phases_stub.py:37** — Loads `simulations/demo-sim` directly:
```python
return load_simulation(Path("simulations/demo-sim"))
```

**Analysis:** These tests are READ-ONLY (mock LLM, don't save). Safe, but could be improved.

**Recommendation:** LOW priority — refactor to use `project_root` fixture if tests ever need modification.

---

## 4. Naming Conventions

### File Naming

All files follow `test_<module>.py` pattern ✅

| Pattern | Files |
|---------|-------|
| `test_<module>.py` | 16 unit, 4 integration |

### Function Naming

All tests follow `test_<what>_<expected>` pattern ✅

**Good examples:**
- `test_load_missing_file_raises_error`
- `test_fallback_logs_warning`
- `test_update_character_location`
- `test_sliding_window_eviction`

**No bad patterns found** (no `test_1`, `test_it_works`, etc.)

### Class Naming

All test classes follow `TestClassName` pattern ✅

Examples:
- `TestConfigLoad`
- `TestPhaseConfig`
- `TestExitCodeConstants`
- `TestChainManagement`

---

## 5. Test Isolation

### Fixture Scopes

```bash
grep -rn "@pytest.fixture.*scope=" tests/
# No matches found
```

All fixtures use default `scope="function"` — each test gets fresh fixture instance ✅

### Global Fixtures (conftest.py)

```python
@pytest.fixture
def project_root() -> Path:
    return Path(__file__).parent.parent

@pytest.fixture
def schemas_dir(project_root: Path) -> Path:
    return project_root / "src" / "schemas"
```

Both return **immutable Path objects** — safe ✅

### Potential Issues

None found. Tests are properly isolated.

---

## Changes Made

1. **test_skeleton.py**: Added `pytestmark = pytest.mark.integration` after imports

```python
# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration
```

---

## Verification

### Before Fix
```
$ pytest tests/ -m "not integration" --collect-only | grep skeleton
tests/integration/test_skeleton.py::test_run_tick_increments_current_tick
tests/integration/test_skeleton.py::test_run_tick_returns_narratives
... (9 tests incorrectly included)
```

### After Fix
```
$ pytest tests/ -m "not integration" --collect-only | grep skeleton
(no output - correct!)
```

### Test Run
```
$ pytest tests/ -m "not integration" -v --tb=short
====================== 349 passed, 32 deselected in 0.65s ======================
```

32 integration tests correctly deselected (including 9 from test_skeleton.py).

---

## Quality Checks

- **ruff check**: PASS
- **ruff format**: PASS
- **pytest**: 381 passed
