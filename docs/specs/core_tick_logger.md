# core_tick_logger.md

## Status: READY

Detailed tick logging for Thing' Sandbox. Writes markdown files with full
phase-by-phase information including token usage, reasoning summaries,
and entity state changes.

---

## Public API

### PhaseData and TickReport

**NOTE:** `PhaseData` and `TickReport` are now defined in `src.runner` and imported here.
See `core_runner.md` for full documentation of these dataclasses.

```python
# Import from runner
from src.runner import PhaseData, TickReport
```

These classes are re-exported from tick_logger for backwards compatibility:
```python
__all__ = ["PhaseData", "TickLogger", "TickReport"]
```

### TickLogger

Class for writing tick logs to markdown files.

```python
class TickLogger:
    def __init__(self, sim_path: Path) -> None
    def write(self, report: TickReport) -> None
```

#### TickLogger.\_\_init\_\_(sim_path) -> None

Initialize logger for a simulation.

- **Input**:
  - sim_path — path to simulation folder
- **Behavior**:
  - Stores sim_path for later use
  - Does not create logs/ directory until write() is called

#### TickLogger.write(report) -> None

Write tick report to markdown file.

- **Input**:
  - report — TickReport with tick data
- **Side effects**:
  - Creates `{sim_path}/logs/` directory if not exists
  - Writes `{sim_path}/logs/tick_NNNNNN.md` (6 digits with leading zeros)
- **Raises**:
  - StorageIOError — if file write fails

---

## Log File Format

File path: `simulations/{sim_id}/logs/tick_NNNNNN.md`

```markdown
# Tick 42

**Simulation:** demo-sim
**Timestamp:** 2025-06-07 14:32
**Duration:** 8.2s

## Summary

| Metric | Value |
|--------|-------|
| Total tokens | 4,566 |
| Reasoning tokens | 1,566 |
| Cached tokens | 890 |
| LLM requests | 8 |

## Phase 1: Intentions

**Duration:** 2.1s | **Tokens:** 1,200 (reasoning: 400)

### Ogilvy
- **Intention:** approach the cylinder cautiously
- **Reasoning:** _"The character's scientific curiosity would override fear..."_

### Henderson
- **Intention:** observe and take notes
- **Reasoning:** _"As a journalist, documenting is the priority..."_

## Phase 2a: Arbitration

**Duration:** 1.8s | **Tokens:** 1,500 (reasoning: 600)

### Horsell Common

**Characters:**
- **ogilvy:** location=horsell_common, state="anxious but determined", intent="examine the cylinder"
- **henderson:** location=horsell_common, state="alert", intent="document everything"

**Location:** moment="The cylinder surface glows faintly", description unchanged

**Reasoning:** _"No conflicts between intentions..."_

### Dark Forest

**Characters:** *(none)*

**Location:** moment unchanged, description unchanged

**Reasoning:** _"The forest remains undisturbed..."_

## Phase 2b: Narratives

**Duration:** 1.2s | **Tokens:** 800 (reasoning: 200)

### Horsell Common

> Ogilvy crept closer to the metallic cylinder, his heart pounding...

### Dark Forest

> The ancient oaks stood silent under the moonless sky...

## Phase 3: State Application

**Duration:** 0.01s | *(no LLM)*

### Characters
- **ogilvy:** location unchanged, state="anxious but determined", intent="examine the cylinder"
- **henderson:** location unchanged, state="alert", intent="document everything"

### Locations
- **horsell_common:** moment="The cylinder surface glows faintly", description unchanged
- **dark_forest:** moment unchanged, description unchanged

## Phase 4: Memory

**Duration:** 3.1s | **Tokens:** 1,066 (reasoning: 366)

### Ogilvy
- **New memory:** "I approached the cylinder..."
- **Cells:** 2/5 (no summarization)

### Henderson
- **New memory:** "Watched Ogilvy approach..."
- **Cells:** 5/5 (summarized)
- **Reasoning:** _"Merging older observations about the crash site..."_
```

---

## Internal Methods

### \_format_header(report) -> str

Format document header with simulation info and summary table.

### \_format_phase1(phase_data, simulation) -> str

Format Phase 1 section (character intentions).
- Per-character subsections
- Extract reasoning from stats.results by parsing entity_key

### \_format_phase2a(phase_data, simulation) -> str

Format Phase 2a section (arbitration).
- Per-location subsections (including empty locations)
- Character updates with state changes
- Location updates
- Reasoning from stats.results

### \_format_phase2b(phase_data, simulation) -> str

Format Phase 2b section (narratives).
- Per-location subsections
- Narrative text in blockquote format

### \_format_phase3(phase_data, simulation) -> str

Format Phase 3 section (state application).
- Character state changes
- Location state changes
- No LLM stats

### \_format_phase4(phase_data, simulation, pending_memories) -> str

Format Phase 4 section (memory update).
- Per-character subsections
- New memory text
- Cell count and summarization status
- Reasoning if summarization occurred

### \_parse_entity_key(entity_key) -> tuple[str, str]

Parse entity_key into (chain_type, entity_id).

```python
"intention:bob" -> ("intention", "bob")
"resolution:tavern" -> ("resolution", "tavern")
```

### \_get_reasoning_for_entity(stats, entity_id, chain_type) -> str | None

Extract reasoning summary text for specific entity from BatchStats.results.
Returns formatted italic quote or None if not found.

### \_had_reasoning_for_entity(stats, entity_id, chain_type) -> bool

Check if reasoning occurred for entity based on `usage.reasoning_tokens > 0`.
This is the reliable indicator — `reasoning_summary` may be empty even when reasoning occurred.

---

## Dependencies

- **Standard Library**: logging, pathlib, typing
- **External**: None
- **Internal**:
  - src.runner (PhaseData, TickReport)
  - src.utils.storage (Simulation, StorageIOError)
  - src.utils.llm (BatchStats)

---

## Usage Examples

### Basic Usage

```python
from pathlib import Path
from datetime import datetime
from src.runner import PhaseData, TickReport
from src.tick_logger import TickLogger

sim_path = Path("simulations/my-sim")
logger = TickLogger(sim_path)

report = TickReport(
    sim_id="my-sim",
    tick_number=42,
    narratives={"tavern": "Bob enters..."},
    location_names={"tavern": "The Tavern"},
    success=True,
    timestamp=datetime.now(),
    duration=8.2,
    phases={
        "phase1": PhaseData(duration=2.1, stats=stats1, data=intentions),
        "phase2a": PhaseData(duration=1.8, stats=stats2a, data=master_results),
        "phase2b": PhaseData(duration=1.2, stats=stats2b, data=narratives),
        "phase3": PhaseData(duration=0.01, stats=None, data=phase3_data),
        "phase4": PhaseData(duration=3.1, stats=stats4, data=None),
    },
    simulation=simulation,
    pending_memories={"bob": "I saw something..."},
)

logger.write(report)
```

### In Runner

```python
class TickRunner:
    async def run_tick(self, sim_id: str) -> TickReport:
        # ... execute phases with duration tracking ...

        # Build unified TickReport
        report = TickReport(...)

        # Write log if enabled
        if self._config.output.file.enabled:
            from src.tick_logger import TickLogger
            logger = TickLogger(sim_path)
            logger.write(report)

        # Call narrators with same report
        self._call_narrators(report)

        return report
```

---

## Test Coverage

### Unit Tests (test_tick_logger.py)

**PhaseData Tests:**
- test_phase_data_creation — creates with all fields

**TickReport Tests:**
- test_tick_report_creation — creates with all fields

**TickLogger Tests:**
- test_tick_logger_creates_logs_dir — creates logs/ if missing
- test_tick_logger_writes_file — writes file with correct name
- test_tick_logger_tick_number_padding — tick 1 → tick_000001.md

**Format Tests:**
- test_tick_logger_format_header — correct header with summary table
- test_tick_logger_format_phase1 — per-character with reasoning
- test_tick_logger_format_phase2a — per-location including empty
- test_tick_logger_format_phase2b — narratives in blockquote
- test_tick_logger_format_phase3 — characters and locations
- test_tick_logger_format_phase4 — memory with cells count

**Edge Cases:**
- test_tick_logger_empty_reasoning — no reasoning line if reasoning_summary is None
- test_tick_logger_summarized_without_reasoning_summary — shows "(summarized)" when reasoning_tokens > 0 but reasoning_summary is None
- test_tick_logger_no_summarization_when_no_reasoning_tokens — shows "(no summarization)" when reasoning_tokens = 0
- test_tick_logger_non_ascii_content — handles Unicode correctly

### Integration Tests (test_skeleton.py)

- test_run_tick_creates_log_file — log file created after tick
- test_run_tick_log_file_disabled — no file if config.output.file.enabled=False

---

## Implementation Notes

### Reasoning Summary Extraction

reasoning_summary is list[str] in RequestResult. Join with space for display:

```python
if reasoning_summary:
    text = " ".join(reasoning_summary)
    return f'_"{text}"_'
```

### Entity Key Parsing

Entity keys follow stable format `"{chain_type}:{entity_id}"`:

```python
def _parse_entity_key(entity_key: str) -> tuple[str, str]:
    chain_type, entity_id = entity_key.split(":", 1)
    return chain_type, entity_id
```

### Summarization Detection

Phase 4 summarization detection uses `reasoning_tokens > 0` as the reliable indicator.

**Important:** `reasoning_summary` may be empty (`None` or `[]`) even when reasoning
actually occurred — this is documented OpenAI API behavior. The reliable indicator
is `usage.reasoning_tokens > 0`.

```python
# Check if reasoning occurred based on tokens, not summary text
had_reasoning = self._had_reasoning_for_entity(stats, char_id, "memory")
reasoning_text = self._get_reasoning_for_entity(stats, char_id, "memory")

if had_reasoning:
    lines.append(f"- **Cells:** {cells}/{max_cells} (summarized)")
    if reasoning_text:
        lines.append(f"- **Reasoning:** {reasoning_text}")
else:
    lines.append(f"- **Cells:** {cells}/{max_cells} (no summarization)")
```

### File Encoding

Write files with UTF-8 encoding for proper Unicode support:

```python
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
```

### Thread Safety

Not thread-safe. Designed for single-threaded execution within one tick.
