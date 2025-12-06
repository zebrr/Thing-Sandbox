# CLAUDE.md - Claude Code Instructions - Project Thing' Sandbox v1.4

Workspace: `/Users/askold.romanov/code/thing-sandbox`

## Project Overview

Thing' Sandbox is an experimental text simulation inspired by D&D/MUD games where AI-controlled characters autonomously interact in a persistent world. The system runs discrete "ticks" — each tick has 4 phases: intention formation, scene resolution by game master, result application, and memory summarization.

The project serves dual purposes: a sandbox for exploring LLM agent behavior and entertainment for a small group of friends through passive observation of AI character interactions.

## Critical Rules

1. **NEVER commit without user approval** — ask before committing, user controls git
2. **NEVER change commit message after user approval** - do not add footer and your signature
3. **NEVER create** directories not specified in architecture
4. **NEVER run** simulation ticks without user permission
5. **ALWAYS backup** files before modification: `<filename>_backup_<TASK-ID>.*`
6. **ALWAYS activate** venv before Python commands: `source .venv/bin/activate` or similar
7. **ALWAYS do** quality checks → tests → spec updates → report (in this order)

## Environment Detection

At session start, detect environment:

### Check 1: Platform
- `$OSTYPE` contains `darwin` → macOS
- `$OSTYPE` contains `msys` or `cygwin` → Windows

### Check 2: Agent SDK Worktree or Terminal mode
- `$PWD` contains `.claude-worktrees` → Agent SDK sandbox mode
  - venv does NOT exist, must create:
    - macOS: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`
    - Windows: `python -m venv .venv && .venv\Scripts\activate && pip install -r requirements-dev.txt`
  - activate venv: `source .venv/bin/activate` (macOS) or `.venv\Scripts\activate` (Windows) 
- Otherwise → normal terminal mode
  - venv EXISTS, activate: `source .venv/bin/activate` (macOS) or `.venv\Scripts\activate` (Windows)

## Project Structure

```
thing-sandbox/
├── docs/                          # project documentation
│   ├── specs/                     # module specifications
│   └── tasks/                     # task assignments and reports
│
├── src/
│   ├── schemas/                   # JSON schemas (documentation, not runtime)
│   ├── prompts/                   # default LLM prompt templates
│   ├── phases/                    # simulation phases
│   │   ├── __init__.py
│   │   ├── common.py              # shared phase utilities (PhaseResult)
│   │   ├── phase1.py              # intentions
│   │   ├── phase2a.py             # scene resolution (arbiter)
│   │   ├── phase2b.py             # narrative generation
│   │   ├── phase3.py              # result application
│   │   └── phase4.py              # memory update
│   ├── utils/                     # reusable components
│   │   ├── __init__.py
│   │   ├── exit_codes.py          # standard exit codes
│   │   ├── llm.py                 # LLM Client facade
│   │   ├── llm_errors.py          # LLM exception hierarchy
│   │   ├── prompts.py             # Jinja2 template renderer
│   │   ├── storage.py             # simulation read/write, Pydantic models
│   │   └── llm_adapters/          # provider-specific adapters
│   │       ├── __init__.py
│   │       ├── base.py            # abstract adapter interface
│   │       └── openai.py          # OpenAI Responses API adapter
│   ├── __init__.py
│   ├── cli.py                     # entry point (typer)
│   ├── config.py                  # configuration loading
│   ├── runner.py                  # tick orchestration
│   └── narrators.py               # output: console, file, telegram
│
├── tests/
│   ├── unit/                      # unit tests
│   ├── integration/               # integration tests
│   └── conftest.py                # pytest fixtures
│
├── simulations/                   # simulation data
│   ├── _templates/                # simulation templates (tracked)
│   └── <sim-id>/                  # active simulations (in .gitignore)
│
├── config.toml                    # application configuration
├── requirements.txt               # runtime dependencies
├── requirements-dev.txt           # dev dependencies
└── pyproject.toml                 # package and tool settings
```

### Key Components

| Component | File | Responsibility |
|-----------|------|----------------|
| CLI | `cli.py` | Entry point, argument parsing |
| Config | `config.py` | Configuration loading, prompt resolution |
| Runner | `runner.py` | Tick orchestration, atomicity |
| Phase 1 | `phases/phase1.py` | Character intention formation |
| Phase 2a | `phases/phase2a.py` | Scene resolution by arbiter |
| Phase 2b | `phases/phase2b.py` | Narrative generation |
| Phase 3 | `phases/phase3.py` | Result application (no LLM) |
| Phase 4 | `phases/phase4.py` | Memory summarization |
| Phase Common | `phases/common.py` | Shared utilities (PhaseResult) |
| LLM Client | `utils/llm.py` | Unified LLM interface facade |
| LLM Errors | `utils/llm_errors.py` | Exception hierarchy for LLM ops |
| LLM Adapter Base | `utils/llm_adapters/base.py` | Abstract adapter interface |
| LLM Adapter OpenAI | `utils/llm_adapters/openai.py` | OpenAI Responses API |
| Prompts | `utils/prompts.py` | Jinja2 template rendering |
| Storage | `utils/storage.py` | Simulation read/write, Pydantic models |
| Narrators | `narrators.py` | Output channels |

### JSON Schemas

Located in `src/schemas/`. These are **documentation artifacts** — the actual validation uses Pydantic models in code. Schemas document the LLM contract for human readers.

| Schema | Purpose |
|--------|---------|
| `Character.schema.json` | Character: identity, state, memory |
| `Location.schema.json` | Location: identity, state, connections |
| `IntentionResponse.schema.json` | Phase 1 LLM output |
| `Master.schema.json` | Phase 2a LLM output |
| `NarrativeResponse.schema.json` | Phase 2b LLM output |
| `SummaryResponse.schema.json` | Phase 4 LLM output |

### Exit Codes

| Code | Constant | When |
|------|----------|------|
| 0 | `EXIT_SUCCESS` | Successful completion |
| 1 | `EXIT_CONFIG_ERROR` | Missing API key, broken config.toml |
| 2 | `EXIT_INPUT_ERROR` | Invalid JSON, schema validation failure |
| 3 | `EXIT_RUNTIME_ERROR` | LLM garbage after retries, unexpected exceptions |
| 4 | `EXIT_API_LIMIT_ERROR` | OpenAI rate limits |
| 5 | `EXIT_IO_ERROR` | Cannot write to simulations/ |

## Documentation First Policy

**ALWAYS** check documentation before reading code:

- `docs/Thing' Sandbox Architecture.md` — project structure, modules, data flow
- `docs/specs/` — module specifications (read only specs relevant to your task)

To create or update specifications use `docs/Thing' Sandbox Specs Writing Guide.md`

If documentation is incomplete or unclear, **ASK** user — don't assume!

### Specification Naming

| Type | Modules | Spec prefix | Example |
|------|---------|-------------|---------|
| Phase | `phases/phase*.py` | `phase_` | `phase1.py` → `phase_1.md` |
| Phase Common | `phases/common.py` | `phase_` | `common.py` → `phase_common.md` |
| Core | `cli.py`, `config.py`, `runner.py`, `narrators.py` | `core_` | `runner.py` → `core_runner.md` |
| Utils | `utils/*.py` | `util_` | `utils/llm.py` → `util_llm.md` |
| Adapters | `utils/llm_adapters/*.py` | `util_llm_adapter_` | `openai.py` → `util_llm_adapter_openai.md` |

## Standard Workflow

1. **READ** task assignment in `docs/tasks/TS-<milestone>-<module>-XXX.md`
2. **CHECK** specifications in `docs/` and `docs/specs/`
3. **PLAN** approach (use `think`, `think hard`, `ultrathink` for complex tasks)
4. **BACKUP** any files you'll modify
5. **CODE** implementation with tests
6. **QUALITY** run checks: `ruff check src/ && ruff format src/ && mypy src/`
7. **TEST** run pytest: `python -m pytest -v`
8. **UPDATE** specifications for modified modules
9. **REPORT** create `docs/tasks/TS-<milestone>-<module>-XXX_REPORT.md`
10. **NEVER** proceed beyond the specified scope

## Communication Guidelines

- Match user's language (Russian for discussion, English for code/docs)
- When uncertain: **ASK**, don't assume
- Explain architectural decisions step by step
- Propose alternatives with pros/cons
- Report blockers immediately

## Commands Reference

```bash
# Environment Setup
source .venv/bin/activate              # Always first
source .venv/bin/activate.fish         # For fish shell
source .venv/bin/activate.csh          # For csh/tcsh

# Quality Checks (run ALL before tests)
ruff check src/                        # Linting
ruff format src/                       # Formatting
mypy src/                              # Type checking

# Testing
python -m pytest -v                       # All tests
python -m pytest -v -s                    # With stdout
python -m pytest -v -m "not integration"  # Skip integration
python -m pytest -v -m "integration"      # Only integration
python -m pytest -k "test_name" -v        # Specific test
python -m pytest tests/test_module.py::test_function -v  # Specific test

# Coverage
python -m pytest --cov=src --cov-report=term-missing -v
```

## Report Template

The report `docs/tasks/TS-<milestone>-<module>-XXX_REPORT.md` should follow this structure:

```markdown
# Task TS-<milestone>-<module>-XXX Completion Report

## Summary
[Brief overview of what was accomplished]

## Changes Made
- File 1: [what changed and why]
- File 2: [what changed and why]

## Tests
- Result: PASS/FAIL
- Existing tests modified: [list if any]
- New tests added: [list if any]

## Quality Checks
- ruff check: PASS/FAIL
- ruff format: PASS/FAIL
- mypy: PASS/FAIL

## Issues Encountered
[Any problems and resolutions, or "None"]

## Next Steps
[If any follow-up needed, or "None"]

## Commit Proposal
`type: brief description`

## Specs Updated
[List of updated specification files, or "None"]
```

## Task Type Patterns

**New Module**:
1. Write spec following `docs/Thing' Sandbox Specs Writing Guide.md`
2. Create tests in `tests/unit/test_<module>.py`
3. Implement in `src/<module>.py`
4. Update spec with implementation details

**Bug Fix**:
1. Reproduce with failing test
2. Fix implementation
3. Verify all tests pass
4. Update affected specs

**Refactoring**:
1. Ensure tests exist
2. Backup original files
3. Refactor incrementally
4. Verify tests still pass

## Appendix 1: Core Python Standards

- Changes to existing code structure require clear, documented justification
- Every new feature must include unit tests
- Every bug must be reproduced by a unit test before being fixed
- Each class must include a docstring stating its purpose with usage example
- Each public method or function should include a docstring
- Docstrings, specs, and comments must be in English, UTF-8 encoding
- Favor "fail fast" over "fail safe": throw exceptions earlier
- Exception messages must include as much context as possible
- Error and log messages should not end with a period
- Constructors (`__init__`) should be lightweight: attribute assignments and simple validation only
- Prefer composition; use inheritance only when it adds clear value
- Favor immutable data objects where practical (e.g., `@dataclass(frozen=True)`)
- Provide only one primary constructor; use `@classmethod` factories for alternatives
- Do not create "utility" classes; use module-level functions instead
- Avoid `@staticmethod`; prefer `@classmethod` or standalone functions

## Appendix 2: Testing Standards

- Every change must be covered by a unit test
- Test cases must be as short as possible
- Every test must assert at least once
- Tests must use irregular inputs (e.g., non-ASCII strings)
- Tests must close resources they use (files, sockets, connections)
- Each test must verify only one specific behavioral pattern
- Tests should store temporary files in temporary directories, not in the codebase
- Tests must not wait indefinitely; always use timeouts
- Tests must assume absence of Internet connection (for unit tests)
- Tests must not rely on default configurations — provide explicit arguments
- Prefer pytest fixtures over `setUp`/`tearDown` methods
- Name tests descriptively: `test_returns_none_if_empty`
- Use mocks sparingly — favor lightweight fakes or stubs
