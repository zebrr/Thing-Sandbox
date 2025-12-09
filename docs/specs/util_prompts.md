# util_prompts.md

## Status: READY

Prompt rendering module for Thing' Sandbox. Loads Jinja2 templates and renders them
with simulation context. Integrates with Config for template resolution.

---

## Public API

### PromptRenderError

Exception raised when prompt rendering fails.

```python
class PromptRenderError(Exception):
    """Raised when prompt rendering fails.
    
    This includes missing variables in context, Jinja2 syntax errors,
    and file read errors.
    """
    pass
```

### PromptRenderer

Main class for loading and rendering prompt templates.

#### PromptRenderer.__init__(config, sim_path)

Initialize renderer with configuration and optional simulation path.

- **Input**:
  - config (Config) — application configuration instance
  - sim_path (Path | None) — path to simulation folder for override resolution
- **Returns**: PromptRenderer instance
- **Side effects**: creates Jinja2 Environment

#### PromptRenderer.render(template_name, context)

Render prompt template with given context.

- **Input**:
  - template_name (str) — template identifier without extension (e.g., "phase1_intention_system")
  - context (dict[str, Any]) — variables for Jinja2 substitution
- **Returns**: str — rendered prompt text
- **Raises**:
  - PromptNotFoundError (from config) — template file not found
  - PromptRenderError — rendering failed (missing variable, syntax error, IO error)

**Resolution order** (delegated to Config.resolve_prompt):
1. `{sim_path}/prompts/{template_name}.md` (if sim_path provided and file exists)
2. `src/prompts/{template_name}.md` (default)

---

## Internal Implementation

### Jinja2 Environment Configuration

```python
Environment(
    undefined=StrictUndefined,   # Error on missing variables
    autoescape=False,            # Markdown output, not HTML
    keep_trailing_newline=True,  # Preserve trailing newlines
)
```

**Rationale:**
- `StrictUndefined` — fail fast on missing context variables, easier debugging
- `autoescape=False` — prompts are Markdown, HTML escaping would break formatting
- `keep_trailing_newline=True` — preserve file formatting

### Template Loading Strategy

Templates are loaded via `from_string()` after reading file content:

```python
template_path = self._config.resolve_prompt(template_name, self._sim_path)
template_source = template_path.read_text(encoding="utf-8")
template = self._env.from_string(template_source)
```

**Why not FileSystemLoader?**
- Resolution logic already exists in `Config.resolve_prompt()`
- Override mechanism (sim prompts → default) is non-trivial for Jinja2 loader
- Avoids duplicating path resolution logic

### Caching

No caching in MVP. Each `render()` call reads and compiles the template.

**Future optimization:** LRU cache by template_path if profiling shows bottleneck.

---

## Error Handling

### Error Mapping

| Situation | Exception | Exit Code |
|-----------|-----------|-----------|
| Template file not found | `PromptNotFoundError` | EXIT_INPUT_ERROR (2) |
| Missing variable in context | `PromptRenderError` | EXIT_INPUT_ERROR (2) |
| Jinja2 syntax error | `PromptRenderError` | EXIT_INPUT_ERROR (2) |
| File read error (permissions, encoding) | `PromptRenderError` | EXIT_IO_ERROR (5) |

### Error Messages

Error messages include template name and specific cause:

```
PromptRenderError: Missing variable in 'phase1_intention_user': 'character' is undefined
PromptRenderError: Syntax error in 'phase2a_resolution_system': unexpected '}'
PromptRenderError: Cannot read 'phase1_intention_system': [Errno 13] Permission denied
```

---

## Context Data Types

### Pydantic Models

Jinja2 accesses attributes via `getattr()`, so Pydantic models work directly:

```python
# Works — no .model_dump() needed
renderer.render("phase1_intention_user", {
    "character": character,  # Pydantic model
    "location": location,    # Pydantic model
    "others": [c1, c2],      # list of Pydantic models
})
```

Template access:
```jinja2
{{ character.identity.name }}
{{ character.memory.cells }}
{% for other in others %}...{% endfor %}
```

### Expected Context by Phase

See `docs/Thing' Sandbox LLM Prompting.md` section 3.2 for complete reference.

| Phase | Key Variables |
|-------|---------------|
| phase1_intention | character, location, others |
| phase2a_resolution | location, characters, intentions, tick |
| phase2b_narrative | location_before, characters_before, intentions, master_result |
| phase4_summary | character, tick |

---

## Dependencies

- **Standard Library**: pathlib
- **External**: jinja2>=3.0.0
- **Internal**: 
  - src.config.Config (for resolve_prompt)
  - src.config.PromptNotFoundError (re-exported for convenience)

---

## Usage Examples

### Basic Rendering

```python
from pathlib import Path
from src.config import Config
from src.utils.prompts import PromptRenderer

config = Config.load()
renderer = PromptRenderer(config, sim_path=Path("simulations/demo-sim"))

# Render system prompt (no variables in default template)
system = renderer.render("phase1_intention_system", {})

# Render user prompt with context
user = renderer.render("phase1_intention_user", {
    "character": character,
    "location": location,
    "others": visible_characters,
})
```

### Without Simulation Override

```python
# Uses only default prompts from src/prompts/
renderer = PromptRenderer(config)  # sim_path=None
```

### Error Handling

```python
from src.utils.prompts import PromptRenderer, PromptRenderError
from src.config import PromptNotFoundError
from src.utils.exit_codes import EXIT_INPUT_ERROR
import logging

logger = logging.getLogger(__name__)

try:
    result = renderer.render("phase1_intention_user", {"character": char})
except PromptNotFoundError as e:
    logger.error("Template not found: %s", e)
    sys.exit(EXIT_INPUT_ERROR)
except PromptRenderError as e:
    logger.error("Render error: %s", e)
    sys.exit(EXIT_INPUT_ERROR)
```

---

## Test Coverage

### Unit Tests

- **test_render_valid_context** — renders template with all required variables
- **test_render_empty_context** — renders template with no variables (system prompts)
- **test_render_missing_variable** — raises PromptRenderError with variable name
- **test_render_syntax_error** — raises PromptRenderError on malformed Jinja2
- **test_render_with_pydantic_model** — Pydantic models work as context values
- **test_render_with_default_filter** — `| default()` works correctly
- **test_render_with_loops** — `{% for %}` iteration works
- **test_render_with_conditionals** — `{% if %}` conditions work

### Integration with Config

- **test_render_simulation_override** — uses sim_path prompt when exists
- **test_render_fallback_to_default** — uses default when sim override missing
- **test_render_prompt_not_found** — raises PromptNotFoundError

### Edge Cases

- **test_render_preserves_trailing_newline** — file ending preserved
- **test_render_unicode_content** — non-ASCII characters handled correctly
- **test_render_nested_model_access** — deep attribute access works

---

## Implementation Notes

### Module Location

`src/utils/prompts.py` — utility module, not a phase.

### Re-exports

For convenience, re-export `PromptNotFoundError` from the module:

```python
# src/utils/prompts.py
from src.config import PromptNotFoundError

__all__ = ["PromptRenderer", "PromptRenderError", "PromptNotFoundError"]
```

### Logging

Use standard `logging` module:
- DEBUG: template path resolved, render started
- No INFO/WARNING — Config.resolve_prompt handles warnings for missing overrides

### Type Hints

Full type hints for public API:

```python
from typing import Any
from pathlib import Path

def render(self, template_name: str, context: dict[str, Any]) -> str: ...
```
