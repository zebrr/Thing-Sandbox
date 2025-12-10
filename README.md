# Thing' Sandbox

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/API-OpenAI-74aa9c.svg)](https://platform.openai.com/)
[![Jinja2](https://img.shields.io/badge/templates-Jinja2-b41717.svg)](https://jinja.palletsprojects.com/)

Experimental LLM-powered text simulation inspired by D&D/MUD games where AI-controlled characters autonomously interact in a persistent world.

## Table of Contents

- [What is This?](#what-is-this)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Demo Simulation](#demo-simulation)
- [Data Formats](#data-formats)
- [Documentation](#documentation)
- [Limitations](#limitations)
- [Development](#development)
- [License](#license)

## What is This?

Thing' Sandbox is an autonomous text simulation where AI characters live their own lives. No human input required — characters form intentions, interact with each other, and the world evolves tick by tick.

**The name** reflects complete uncertainty about what will emerge. It's an experiment, not a product.

**Two purposes:**
- A sandbox for exploring LLM agent behavior — how do they form goals, remember events, adapt to each other?
- Entertainment for a small group of friends — watch stories unfold through passive observation

**What makes it different from chatbots:**
- Characters don't respond to you — they respond to each other and the world
- No scripted scenarios — emergent behavior from character personalities and circumstances
- Persistent memory that degrades over time — characters forget, misremember, compress history
- Separation of objective world state and subjective character perception

## Key Features

### Subjective Memory System

Each character maintains their own memory as a FIFO queue of detailed recent events plus a compressed summary of distant past. When memory overflows, the oldest detailed event merges into the summary — and information degrades.

Characters don't just store facts. They store interpretations: "I tried to talk to Bob, but he left without answering — he seems to be avoiding me." Different characters remember the same event differently.

Over time, details blur. A character might remember they had a conflict with someone, but forget exactly what was said. This mimics human memory and creates interesting narrative consequences.

### World Context Management

The system maintains strict separation between:
- **Objective world state** — locations, objects, what actually exists
- **Character perception** — what each character knows, believes, remembers

Characters can only perceive what's explicitly in their environment. They don't know other characters' thoughts or goals (unless revealed through interaction). They don't know they're in a simulation.

The Game Master (arbiter) knows everything. Characters know only their slice.

### Dual-Layer Character Goals

Each character has two goal layers:
- **Internal state** — emotions, feelings, current mood ("anxious", "curious", "exhausted")
- **External intent** — conscious goals and focus ("find water", "investigate the cylinder", "avoid the stranger")

These layers interact. A character might intend to investigate something dangerous, but their internal fear affects how they approach it. The arbiter considers both when resolving scenes.

### Living World

Every location processes every tick, even when empty. Fire burns down, rain falls, food rots. The world doesn't pause waiting for characters to arrive.

## How It Works

### The Tick Cycle

Simulation advances in discrete ticks. Each tick runs four phases:

```
Phase 1: Intentions
    Each character decides what they want to do
    Input: character state, memory, current location, who else is here
    Output: intention text

Phase 2a: Resolution  
    Game Master resolves all intentions in each location
    Determines success/failure, handles conflicts, applies triggers
    Output: state changes, memory entries for each character

Phase 2b: Narrative
    Generate human-readable story of what happened
    Output: prose description for the observer log

Phase 3: Application
    Apply all changes to simulation state
    No LLM calls — pure mechanics

Phase 4: Memory
    Compress overflowing memories into summaries
    FIFO shift of memory cells
    Output: updated character memories
```

### Cost Per Tick

```
Phase 1:  N requests (one per character)
Phase 2:  2L requests (arbiter + narrator per location)
Phase 4:  N requests (memory summarization per character)

Total: 2N + 2L requests per tick
```

Where N = number of characters, L = number of locations.

### Atomicity

Either the entire tick completes, or nothing changes. No partial states. If any phase fails critically, the tick restarts from scratch. Graceful degradation handles individual failures (one character's LLM call fails → that character idles this tick).

## Architecture

### Component Layers

```
CLI (cli.py)
    Entry point, parses arguments
    ↓
Runner (runner.py)
    Orchestrates tick: load → phases 1,2a,2b,3,4 → save
    Ensures atomicity, calls narrators
    ↓
Phases (phases/)
    phase1.py — character intentions
    phase2a.py — scene resolution (arbiter)
    phase2b.py — narrative generation
    phase3.py — state application (no LLM)
    phase4.py — memory summarization
    ↓
LLM Client (utils/llm.py)
    Provider-agnostic facade
    Batch execution, response chains, usage tracking
    ↓
OpenAI Adapter (utils/llm_adapters/openai.py)
    Transport layer: API calls, retry, timeout handling
    Structured Outputs for guaranteed valid JSON
```

### Data Flow

```
Storage loads simulation
    ↓
Runner passes data to phases
    ↓
Phases render prompts (Jinja2) and call LLM Client
    ↓
LLM Client batches requests through adapter
    ↓
Responses validated via Pydantic schemas
    ↓
Phase 3 applies changes to in-memory state
    ↓
Storage saves atomically at tick end
```

### Strict Separation

- **Phases** know prompts, schemas, business logic. They don't know OpenAI exists.
- **LLM Client** knows about batching, chains, usage. It doesn't know prompt content.
- **Adapter** knows OpenAI API details. It doesn't leak outside utils/.

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key with access to GPT-5 family models
- Telegram Bot token (optional, for Telegram output)

### Installation

```bash
git clone https://github.com/yourusername/thing-sandbox.git
cd thing-sandbox

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your OPENAI_API_KEY etc
```

### First Run

```bash
# Reset demo simulation to initial state
python -m src.cli reset demo-sim

# Run one tick
python -m src.cli run demo-sim

# Check what happened
cat simulations/demo-sim/logs/tick_000001.md
```

## Configuration

### config.toml

Global application settings in project root.

```toml
[simulation]
memory_cells = 5              # K detailed memory slots per character

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
response_chain_depth = 0      # 0 = independent requests

[phase2a]
model = "gpt-5.1-2025-11-13"
is_reasoning = true
timeout = 600
max_retries = 3
reasoning_effort = "medium"
response_chain_depth = 2      # Keep context between ticks

[phase2b]
model = "gpt-5-mini-2025-08-07"
# ... similar to phase1

[phase4]
model = "gpt-5-mini-2025-08-07"
# ... similar to phase1

[output.console]
show_narratives = true

[output.file]
enabled = true

[output.telegram]
enabled = false
chat_id = ""
mode = "none"              # none | narratives | narratives_stats | full | full_stats
group_intentions = true
group_narratives = true
```

### Environment Variables

```bash
# .env
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...      # optional, for Telegram output
TELEGRAM_TEST_CHAT_ID=...   # optional, for integration tests
```

### Custom Prompts

Override any prompt for a specific simulation:

```
simulations/my-sim/prompts/phase1_intention_system.md  → overrides default
simulations/my-sim/prompts/phase2b_narrative_system.md → overrides default
```

If not found in simulation folder, falls back to `src/prompts/`.

## Usage

### CLI Commands

```bash
# Run one tick
python -m src.cli run <sim-id>

# Check simulation status
python -m src.cli status <sim-id>

# Reset to template state
python -m src.cli reset <sim-id>
```

### Running Multiple Ticks

Continuous/scheduled execution is in the backlog. For now, a simple workaround:

```bash
for i in {1..10}; do python -m src.cli run demo-sim; done
```

### Output

Each tick produces:
- Console output with phase summaries and token usage
- `logs/tick_NNNNNN.md` with detailed breakdown per phase
- Updated character and location JSON files

## Demo Simulation

`demo-sim` is a test simulation inspired by H.G. Wells' "War of the Worlds" — Victorian England, 1898. Two characters (an astronomer and a journalist) encounter a mysterious cylinder on Horsell Common. The setting, tone, and narrative style match late Victorian prose.

### What to Expect

Run a few ticks and watch the characters react to the situation. They don't know what's in the cylinder. They form theories, interact with each other, make decisions based on their personalities and growing memories.

The narrative style matches late Victorian prose. Characters speak and think appropriately for the era.

## Data Formats

### Schemas

All data structures defined in `src/schemas/`:

| Schema | Purpose |
|--------|---------|
| `Character.schema.json` | Character: identity, state, memory |
| `Location.schema.json` | Location: identity, state, connections |
| `IntentionResponse.schema.json` | Phase 1 output |
| `Master.schema.json` | Phase 2a output (arbiter decisions) |
| `NarrativeResponse.schema.json` | Phase 2b output |
| `SummaryResponse.schema.json` | Phase 4 output |

### Simulation Structure

```
simulations/my-sim/
    simulation.json       # tick counter, status
    characters/
        alice.json
        bob.json
    locations/
        tavern.json
        forest.json
    logs/
        tick_000001.md
        tick_000002.md
    prompts/              # optional overrides
```

## Documentation

| Path | Contents |
|------|----------|
| `docs/Thing' Sandbox Concept.md` | Core concept, tick structure, memory system |
| `docs/Thing' Sandbox Architecture.md` | Technical architecture, modules, config |
| `docs/Thing' Sandbox LLM Approach v2.md` | LLM integration: adapters, chains, batching |
| `docs/Thing' Sandbox LLM Prompting.md` | Prompt design principles and templates |
| `docs/specs/` | Module specifications |
| `src/prompts/` | Default Jinja2 prompt templates |
| `src/schemas/` | JSON schemas for validation |

## Limitations

- **Memory-bound** — entire simulation state in memory
- **Sequential ticks** — no parallel tick execution (by design — causality matters)
- **API-dependent** — requires stable OpenAI API access
- **Single provider** — currently OpenAI only (architecture supports multiple)
- **No UI** — CLI, log files, and optional Telegram output

## Development

### Code Quality

```bash
ruff check src/
ruff format src/
mypy src/
```

### Running Tests

```bash
# All tests except integration (fast)
pytest tests/ -v -m "not integration"

# Full suite including real API calls
pytest tests/ -v
```

Integration tests require `OPENAI_API_KEY` in environment.

### Project Structure

```
src/
    cli.py              # Entry point
    config.py           # Configuration loading
    runner.py           # Tick orchestration
    narrators.py        # Output: console, Telegram
    tick_logger.py      # Detailed markdown logs
    phases/             # Tick phases
    utils/              # Shared components
    prompts/            # Jinja2 templates
    schemas/            # JSON schemas
simulations/
    _templates/         # Template simulations for reset
        demo-sim/       # Demo simulation template
    demo-sim/           # Working simulation (created by reset)
tests/
    unit/               # Fast, isolated tests
    integration/        # Real API tests
```

### Contributing

1. Follow TDD approach - write tests first
2. All functions must have type hints
3. Run quality checks before commits
4. Update relevant specifications in `/docs/specs/`

## License

MIT License

Copyright (c) 2025 Askold Romanov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.