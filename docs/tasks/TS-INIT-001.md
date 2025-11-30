# TS-INIT-001: Initialize Project Structure

## References

- `docs/Thing' Sandbox Architecture.md` — project structure, dependencies, configuration
- `CLAUDE.md` — development standards and workflow

## Context

This is the foundational task for Thing' Sandbox project. The goal is to set up the complete project infrastructure: package configuration, dependencies, directory structure, and tooling configuration.

Currently exists:
- `docs/` with architecture, concept, specs guide, workplan
- `docs/specs/util_exit_codes.md` — exit codes specification
- `src/schemas/` with 6 JSON schema files
- `CLAUDE.md`, `README.md`, `.gitignore`, `.env`

After this task, the project should have a working Python environment where all dev tools run successfully (even on empty/minimal source files).

## Steps

### 1. Create `pyproject.toml`

Package metadata and tool configuration:

```toml
[project]
name = "thing-sandbox"
version = "0.1.0"
description = "Experimental LLM-powered text simulation"
requires-python = ">=3.11"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
]
```

### 2. Create `requirements.txt`

Runtime dependencies:

```
typer>=0.9.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
openai>=1.0.0
jsonschema>=4.0.0
tomli>=2.0.0;python_version<"3.11"
```

### 3. Create `requirements-dev.txt`

Development dependencies:

```
-r requirements.txt
pytest>=7.0.0
pytest-cov>=4.0.0
mypy>=1.0.0
ruff>=0.1.0
```

### 4. Create `.env.example`

Template for environment variables:

```
# OpenAI API Key (required for LLM calls)
OPENAI_API_KEY=your_api_key_here

# Telegram Bot Token (optional, for Telegram narrator)
TELEGRAM_BOT_TOKEN=
```

### 5. Create `config.toml`

Application configuration stub:

```toml
[llm]
# LLM client parameters will be added later

[simulation]
memory_cells = 5
```

### 6. Create directory structure

Create the following with `__init__.py` files:

```
src/
├── __init__.py          # empty, marks package
├── utils/
│   └── __init__.py      # empty, marks package
└── prompts/             # empty directory (no __init__.py, not a package)
```

### 7. Create `tests/conftest.py`

Pytest configuration with basic fixtures:

```python
"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def schemas_dir(project_root: Path) -> Path:
    """Return the schemas directory."""
    return project_root / "src" / "schemas"
```

### 8. Update `.gitignore`

Ensure the following entries exist (add if missing):

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/

# Virtual environment
.venv/
venv/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env

# Project specific
simulations/

# Testing
.coverage
htmlcov/
.pytest_cache/

# mypy
.mypy_cache/

# ruff
.ruff_cache/
```

### 9. Update `README.md`

Add setup instructions section. Keep existing content, add:

```markdown
## Setup

### Prerequisites

- Python 3.11 or higher
- pip

### Installation

1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

### Development

Run quality checks:
```bash
ruff check src/
ruff format src/
mypy src/
```

Run tests:
```bash
pytest -v
```

## Testing

After completing all steps, verify:

```bash
# Activate venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements-dev.txt

# Run quality checks (should pass with no errors)
ruff check src/
ruff format src/
mypy src/

# Run tests (should show 0 tests collected, no errors)
pytest -v
```

**Expected output:**
- `pip install` completes without errors
- `ruff check src/` — no errors (empty files are valid)
- `ruff format src/` — no changes needed
- `mypy src/` — no errors
- `pytest -v` — "0 items collected" or similar, no errors

## Deliverables

### Files to create:
- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`
- `.env.example`
- `config.toml`
- `src/__init__.py`
- `src/utils/__init__.py`
- `src/prompts/` (empty directory)
- `tests/conftest.py`

### Files to update:
- `.gitignore` (add missing entries)
- `README.md` (add Setup section)

### Report:
- `docs/tasks/TS-INIT-001_REPORT.md`
