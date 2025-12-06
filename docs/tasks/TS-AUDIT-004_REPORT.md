# Audit Report: Code Consistency

## Summary

Overall code consistency is **GOOD**. Most patterns are uniform across modules.

**Key findings:**
- ✅ Config usage: consistent (DI pattern)
- ✅ Path handling: consistent (pathlib + `/` operator)
- ✅ Exit codes: fully consistent (all use constants)
- ✅ Typing: consistent (modern `X | None` syntax)
- ✅ Logger setup: consistent (`logging.getLogger(__name__)`)
- ⚠️ Logging: **print + logging duplication** in phase1/phase3
- ⚠️ Pydantic: Field() usage inconsistent in LLM response models
- ⚠️ Config: `_project_root` accessed directly (should be public or via method)

---

## 1. Config Usage

| Module | How gets Config | Access pattern | Hardcoded values |
|--------|-----------------|----------------|------------------|
| cli.py | `Config.load()` | Direct | None |
| runner.py | DI (parameter) | Direct (`self._config.phase1`) | None |
| phase1.py | DI | `config._project_root` | None |
| phase2a.py | DI | Not used (stub) | None |
| phase2b.py | DI | Not used (stub) | None |
| phase3.py | DI | Not used (stub) | None |
| phase4.py | DI | Not used (stub) | None |
| prompts.py | DI (constructor) | `self._config.resolve_prompt()` | None |
| openai.py | DI (PhaseConfig) | `self.config.*` | `os.environ["OPENAI_API_KEY"]` |

**Verdict**: ✅ Consistent. Config loaded once in CLI, passed via DI everywhere.

**Note**: `_project_root` is private (underscore) but accessed from phase1.py, runner.py, cli.py:
```python
# phase1.py:99
sim_path = config._project_root / "simulations" / simulation.id
```

---

## 2. Pydantic Models

### Config models

| Model | Field() | ConfigDict | Frozen |
|-------|---------|------------|--------|
| SimulationConfig | ✅ `Field(ge=, le=)` | — | No |
| PhaseConfig | ✅ `Field(ge=, le=)` | — | No |
| EnvSettings | — | — | No |

### Storage models

| Model | Field() | ConfigDict | Frozen |
|-------|---------|------------|--------|
| CharacterIdentity | — | `extra="allow"` | No |
| MemoryCell | — | `extra="allow"` | No |
| CharacterMemory | — | `extra="allow"` | No |
| CharacterState | — | `extra="allow"` | No |
| Character | — | `extra="allow"` | No |
| LocationConnection | — | `extra="allow"` | No |
| LocationIdentity | — | `extra="allow"` | No |
| LocationState | — | `extra="allow"` | No |
| Location | — | `extra="allow"` | No |
| Simulation | — | `extra="allow"` | No |

### LLM response models

| Model | Field() | ConfigDict | Frozen |
|-------|---------|------------|--------|
| IntentionResponse | ✅ `Field(min_length=1)` | — | No |
| CharacterUpdate | — | — | No |
| LocationUpdate | — | — | No |
| MasterOutput | — | — | No |

**Findings:**
- Storage models: all use `ConfigDict(extra="allow")` — ✅ consistent
- Config models: all use Field() for constraints — ✅ consistent
- LLM response models: only IntentionResponse uses Field() — ⚠️ inconsistent
- No frozen models anywhere — acceptable for mutable simulation state

---

## 3. Path Handling

| Module | Uses Path | Operator | Hardcoded folder names |
|--------|-----------|----------|------------------------|
| cli.py | ✅ | `/` | — |
| runner.py | ✅ | `/` | "simulations" |
| config.py | ✅ | `/` | "src/prompts", "pyproject.toml", ".env" |
| storage.py | ✅ | `/` | "characters", "locations", "simulation.json", "_templates", "logs" |
| prompts.py | ✅ | `/` | — |
| phase1.py | ✅ | `/` | "simulations" |
| phase3.py | — | — | — |

**Verdict**: ✅ Fully consistent. All use `pathlib.Path` with `/` operator.

Hardcoded folder names are design constants, not issues.

---

## 4. LLM Client Usage

| Phase | Imports from | Creates LLMRequest | Handles batch |
|-------|-------------|-------------------|---------------|
| phase1 | `src.utils.llm`, `src.utils.llm_errors` | ✅ | ✅ `isinstance(result, LLMError)` |
| phase2a | `src.utils.llm` | — (stub) | — |
| phase2b | `src.utils.llm` | — (stub) | — |
| phase3 | — (no LLM) | — | — |
| phase4 | `src.utils.llm` | — (stub) | — |

**Verdict**: ✅ Consistent.
- No direct `openai` imports in phases
- Proper error handling pattern in phase1

---

## 5. Storage Usage

| Module | Functions used | Error handling |
|--------|---------------|----------------|
| cli.py | `load_simulation`, `reset_simulation` | Catches all: `SimulationNotFoundError`, `InvalidDataError`, `StorageIOError`, `TemplateNotFoundError` |
| runner.py | `load_simulation`, `save_simulation` | Propagates to CLI |

**Verdict**: ✅ Consistent. CLI is the error boundary, runner propagates.

---

## 6. Error Handling

### 6.1 Exception Types Inventory

| Exception | Defined in | Raised in | Caught in |
|-----------|-----------|-----------|-----------|
| ConfigError | config.py | config.py | cli.py |
| PromptNotFoundError | config.py | config.py | (propagates) |
| PromptRenderError | prompts.py | prompts.py | (propagates) |
| SimulationNotFoundError | storage.py | storage.py | cli.py |
| InvalidDataError | storage.py | storage.py | cli.py |
| StorageIOError | storage.py | storage.py | cli.py |
| TemplateNotFoundError | storage.py | storage.py | cli.py |
| SimulationBusyError | runner.py | runner.py | cli.py |
| PhaseError | runner.py | runner.py | cli.py |
| LLMError | llm_errors.py | llm.py, openai.py | phase1.py (in batch) |
| LLMRefusalError | llm_errors.py | openai.py | (propagates) |
| LLMIncompleteError | llm_errors.py | openai.py | (propagates) |
| LLMRateLimitError | llm_errors.py | openai.py | (propagates) |
| LLMTimeoutError | llm_errors.py | openai.py | (propagates) |

### 6.2 Error Handling Patterns

| Pattern | Where | Example |
|---------|-------|---------|
| Catch + exit code | cli.py | `except ConfigError → EXIT_CONFIG_ERROR` |
| Catch + wrap | runner.py | `if not result.success → raise PhaseError(...)` |
| Catch + re-raise with context | storage.py | `except json.JSONDecodeError → raise InvalidDataError(f"Invalid JSON in {path}: {e}")` |
| Return error in list | llm.py | `create_batch() → list[T | LLMError]` |
| Catch + fallback + log | phase1.py | `isinstance(result, LLMError) → fallback to idle` |

### 6.3 Error Messages

**Good examples:**
```python
# With context
raise InvalidDataError(f"Invalid JSON in {file_path}: {e}", file_path)
raise PhaseError("phase1", result.error or "Unknown error")
raise StorageIOError(f"Cannot write {sim_file}: {e}", sim_file, e)
```

**Consistent format:** `"{Action} failed: {context}"` or `"{Context}: {error}"`

**Verdict**: ✅ Error handling is well-structured with proper hierarchy.

---

## 7. Logging

### 7.1 Logger Setup

All modules use the same pattern:
```python
logger = logging.getLogger(__name__)
```

**Modules with logger:**
- config.py ✅
- runner.py ✅
- storage.py ✅
- prompts.py ✅
- narrators.py ✅
- phase1.py ✅
- phase3.py ✅
- llm.py ✅
- openai.py ✅

**Verdict**: ✅ Fully consistent.

### 7.2 Log Levels Usage

| Level | Module | For what |
|-------|--------|----------|
| DEBUG | All | Detailed operations (config loaded, chain ops, request details) |
| INFO | runner.py | Key milestones (simulation saved) |
| INFO | storage.py | Reset completed |
| WARNING | config.py | Prompt override not found |
| WARNING | phase1.py | Fallback to idle |
| WARNING | phase3.py | Unknown location/character |
| WARNING | openai.py | Rate limit retry, delete failed |
| WARNING | narrators.py | Output failed |
| ERROR | storage.py | Before raising exceptions |
| ERROR | openai.py | Before raising exceptions |

**Verdict**: ✅ Levels used appropriately.

### 7.3 Print vs Logging

| Module | print() | logging | Issue |
|--------|---------|---------|-------|
| cli.py | `typer.echo()` | — | OK (CLI output) |
| narrators.py | `print()` | `logger.warning` | OK (print is the output) |
| phase1.py | `print()` ⚠️ | `logger.warning` | **DUPLICATE** |
| phase3.py | `print()` ⚠️ | `logger.warning/debug` | **DUPLICATE** |

**Issue found in phase1.py:117-125 and 166-167:**
```python
logger.warning("Phase 1: %s fallback to idle (invalid location: %s)", ...)
print(f"⚠️  Phase 1: {char_id} fallback to idle (invalid location: {char.state.location})")
```

Same message logged AND printed — user sees it twice if logging goes to console.

**Issue found in phase3.py:54-58, 76-84, 91-99:**
```python
logger.warning("Phase 3: unknown location '%s'...", location_id)
print(f"⚠️  Phase 3: unknown location '{location_id}'...")
```

---

## 8. Exit Codes Usage

| Location | Exception | Exit Code | Correct? |
|----------|-----------|-----------|----------|
| cli.py:57 | ConfigError | EXIT_CONFIG_ERROR (1) | ✅ |
| cli.py:63 | SimulationNotFoundError | EXIT_INPUT_ERROR (2) | ✅ |
| cli.py:66 | InvalidDataError | EXIT_INPUT_ERROR (2) | ✅ |
| cli.py:69 | SimulationBusyError | EXIT_RUNTIME_ERROR (3) | ✅ |
| cli.py:72 | PhaseError | EXIT_RUNTIME_ERROR (3) | ✅ |
| cli.py:75 | StorageIOError | EXIT_IO_ERROR (5) | ✅ |
| cli.py:106 | ConfigError | EXIT_CONFIG_ERROR (1) | ✅ |
| cli.py:114 | SimulationNotFoundError | EXIT_INPUT_ERROR (2) | ✅ |
| cli.py:117 | InvalidDataError | EXIT_INPUT_ERROR (2) | ✅ |
| cli.py:128 | (success) | EXIT_SUCCESS (0) | ✅ |
| cli.py:145 | ConfigError | EXIT_CONFIG_ERROR (1) | ✅ |
| cli.py:152 | TemplateNotFoundError | EXIT_INPUT_ERROR (2) | ✅ |
| cli.py:155 | StorageIOError | EXIT_IO_ERROR (5) | ✅ |
| cli.py:157 | (success) | EXIT_SUCCESS (0) | ✅ |

**Verdict**: ✅ All exit codes use constants, no hardcoded numbers.

**Note**: `EXIT_API_LIMIT_ERROR` (4) is defined but never used. `LLMRateLimitError` maps to `EXIT_RUNTIME_ERROR` (via `PhaseError`). This is acceptable — rate limit is a runtime error from user perspective.

---

## 9. Typing

### Type hints coverage
All functions have type hints — ✅

### Union syntax
Modern `X | None` everywhere (not `Optional[X]`) — ✅

### Generic types

| Where | Pattern |
|-------|---------|
| llm.py | `T = TypeVar("T", bound=BaseModel)` |
| llm_adapters/base.py | `T = TypeVar("T", bound=BaseModel)` |
| llm_adapters/openai.py | `T = TypeVar("T", bound=BaseModel)` |
| llm_adapters/base.py | `AdapterResponse(Generic[T])` |

**Verdict**: ✅ Consistent generic usage.

### `Any` usage

| Where | Why | Justified? |
|-------|-----|------------|
| PhaseResult.data | Phase outputs vary (dict, None, Pydantic) | ✅ |
| ResponseChainManager entities | `model_dump()` returns dict | ✅ |
| PromptRenderer.render context | Jinja2 context is dynamic | ✅ |

All `Any` usages are at boundaries where type varies — acceptable.

---

## ✅ Consistent

1. **Config loading**: `Config.load()` in CLI, DI everywhere else
2. **Path handling**: All use `pathlib.Path` with `/` operator
3. **Exit codes**: All use constants from `exit_codes.py`
4. **Logger setup**: All use `logging.getLogger(__name__)`
5. **Typing style**: Modern `X | None` syntax throughout
6. **Error hierarchy**: Well-structured exception inheritance
7. **Storage model config**: All use `ConfigDict(extra="allow")`

---

## ⚠️ Inconsistent

### 1. Print + logging duplication (CRITICAL)

**Files**: `phase1.py`, `phase3.py`

Same warning messages output via both `print()` and `logger.warning()`.

**Impact**: User sees duplicate messages when logging to console.

### 2. Field() usage in LLM response models

**Files**: `phase1.py` (IntentionResponse), `phase2a.py` (CharacterUpdate, LocationUpdate, MasterOutput)

Only IntentionResponse uses `Field(min_length=1)`, other models have no constraints.

**Impact**: Low. Other models are stubs, will be fixed during implementation.

### 3. Private attribute `_project_root` accessed externally

**Files**: `cli.py`, `runner.py`, `phase1.py`

`config._project_root` is accessed despite underscore prefix.

**Impact**: Low. Works, but violates naming convention.

---

## ❌ Issues

None critical.

---

## 📋 Recommendations

### Quick Fixes

1. **Remove duplicate print() in phase1.py and phase3.py**

   Keep only `logger.warning()`, remove `print()` calls for warnings:
   ```python
   # phase1.py:122-125 — DELETE these lines
   print(f"⚠️  Phase 1: {char_id} fallback to idle ...")

   # phase3.py:58, 81-84, 96-99 — DELETE these lines
   print(f"⚠️  Phase 3: ...")
   ```

   If console output needed, configure logging handler instead.

2. **Make `_project_root` public or add property**

   Either rename to `project_root` (no underscore) or add property:
   ```python
   @property
   def project_root(self) -> Path:
       return self._project_root
   ```

### Standards Needed

3. **Field() in LLM response models** — defer until implementing phases 2a, 2b, 4

   When implementing, add `Field()` with constraints matching JSON schemas.

4. **Consider frozen models for immutable data**

   CharacterIdentity, LocationIdentity could be frozen. Discuss if worth the effort.
