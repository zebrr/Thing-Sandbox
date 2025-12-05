# TS-B.0d-PROMPTS-001: Implement Prompt Renderer

## References

**Must read before start:**
- `docs/specs/util_prompts.md` — specification for this module
- `docs/specs/core_config.md` — Config.resolve_prompt() API
- `docs/Thing' Sandbox LLM Prompting.md` — Jinja2 syntax and context objects

**Reference materials:**
- `src/config.py` — existing implementation of resolve_prompt()
- `src/prompts/` — example templates with Jinja2

## Context

Part B.0d of the workplan. We need a module to load and render Jinja2 prompt templates.

**Current state:**
- `Config.resolve_prompt()` already handles template path resolution (sim override → default)
- Prompt templates exist in `src/prompts/` and `simulations/_templates/demo-sim/prompts/`
- Templates use Jinja2 syntax with variables like `{{ character.identity.name }}`

**Goal:**
- Create `PromptRenderer` class that integrates with Config
- Render templates with Pydantic models as context (no .model_dump() needed)
- Fail fast on missing variables (StrictUndefined)

## Steps

### 1. Create module `src/utils/prompts.py`

Implement according to `docs/specs/util_prompts.md`:

```python
"""Prompt rendering module for Thing' Sandbox."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

from src.config import Config, PromptNotFoundError

logger = logging.getLogger(__name__)


class PromptRenderError(Exception):
    """Raised when prompt rendering fails."""
    pass


class PromptRenderer:
    """Loads and renders Jinja2 prompt templates."""
    
    def __init__(self, config: Config, sim_path: Path | None = None) -> None:
        # ... implementation
    
    def render(self, template_name: str, context: dict[str, Any]) -> str:
        # ... implementation


# Re-export for convenience
__all__ = ["PromptRenderer", "PromptRenderError", "PromptNotFoundError"]
```

**Key implementation details:**
- Use `Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)`
- Delegate path resolution to `self._config.resolve_prompt(template_name, self._sim_path)`
- Read file with `template_path.read_text(encoding="utf-8")`
- Compile template with `self._env.from_string(template_source)`
- Catch `UndefinedError` and `TemplateSyntaxError`, wrap in `PromptRenderError`
- Catch file IO errors, wrap in `PromptRenderError`

### 2. Update `src/utils/__init__.py`

Add import for the new module (if pattern exists in the project).

### 3. Create tests `tests/unit/test_prompts.py`

Required test cases from spec:

**Basic rendering:**
- `test_render_valid_context` — full context, successful render
- `test_render_empty_context` — system prompt with no variables
- `test_render_with_pydantic_model` — Pydantic model as context value

**Jinja2 features:**
- `test_render_with_default_filter` — `| default()` works
- `test_render_with_loops` — `{% for %}` iteration
- `test_render_with_conditionals` — `{% if %}` conditions
- `test_render_nested_model_access` — `character.identity.name`

**Error handling:**
- `test_render_missing_variable` — raises PromptRenderError
- `test_render_syntax_error` — raises PromptRenderError on malformed Jinja2
- `test_render_prompt_not_found` — raises PromptNotFoundError

**Config integration:**
- `test_render_simulation_override` — uses sim prompt when exists
- `test_render_fallback_to_default` — uses default when override missing

**Edge cases:**
- `test_render_preserves_trailing_newline` — file ending preserved
- `test_render_unicode_content` — non-ASCII characters

**Test fixtures needed:**
- Temporary directory with test templates
- Mock Pydantic models (or use real ones from `src/utils/storage.py`)
- Config instance with custom project_root pointing to temp dir

### 4. Update spec status

Change `docs/specs/util_prompts.md` status from DRAFT to READY after tests pass.

## Testing

```bash
# Activate venv first
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Quality checks
ruff check src/utils/prompts.py tests/unit/test_prompts.py
ruff format src/utils/prompts.py tests/unit/test_prompts.py
mypy src/utils/prompts.py

# Run tests
pytest tests/unit/test_prompts.py -v

# Verify with existing templates
python -c "
from pathlib import Path
from src.config import Config
from src.utils.prompts import PromptRenderer

config = Config.load()
renderer = PromptRenderer(config)

# Should work - system prompt has no required variables
result = renderer.render('phase1_intention_system', {})
print('System prompt rendered, length:', len(result))

# Should fail - user prompt needs context
try:
    renderer.render('phase1_intention_user', {})
except Exception as e:
    print('Expected error:', type(e).__name__, str(e)[:80])
"
```

**Expected output:**
```
System prompt rendered, length: ~800
Expected error: PromptRenderError Missing variable in 'phase1_intention_user': ...
```

## Deliverables

1. **Module:** `src/utils/prompts.py`
2. **Tests:** `tests/unit/test_prompts.py`
3. **Updated spec:** `docs/specs/util_prompts.md` (status: READY)
4. **Report:** `docs/tasks/TS-B.0d-PROMPTS-001_REPORT.md`

Report should include:
- Summary of implementation
- Test results (pytest output)
- Any deviations from spec
- Quick verification with real templates (use demo-sim)
