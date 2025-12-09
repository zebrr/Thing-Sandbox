# core_narrators.md

## Status: READY

Output handlers for Thing' Sandbox. Narrators receive tick reports and deliver
narratives to various destinations: console, Telegram, web.

Note: File logging is handled separately by TickLogger (see `core_tick_logger.md`).

---

## Public API

### Narrator Protocol

Interface that all narrators must implement.

```python
class Narrator(Protocol):
    def output(self, report: TickReport) -> None:
        """Output tick report to destination."""
        ...

    def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
        """Called when tick execution begins."""
        ...

    def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """Called after each phase completes successfully."""
        ...
```

#### Narrator.output(report: TickReport) -> None

Output tick report to destination.

- **Input**: report — TickReport from completed tick
- **Side effects**: Writes to destination (stdout, network)

#### Narrator.on_tick_start(sim_id: str, tick_number: int, simulation: Simulation) -> None

Called when tick execution begins (after status set to "running").

- **Input**:
  - sim_id — Simulation identifier
  - tick_number — Tick number about to execute (current_tick + 1)
  - simulation — Simulation instance with characters and locations
- **Side effects**: Implementation-specific (e.g., storing simulation reference)
- **Note**: Default implementations should be no-op

#### Narrator.on_phase_complete(phase_name: str, phase_data: PhaseData) -> None

Called after each phase completes successfully.

- **Input**:
  - phase_name — Name of completed phase (phase1, phase2a, phase2b, phase3, phase4)
  - phase_data — PhaseData with duration, stats, and phase output
- **Side effects**: Implementation-specific (e.g., progress display)
- **Note**: Default implementations should be no-op

**Error handling:**
- Narrator errors are logged but don't affect tick success
- Failed narrator doesn't prevent other narrators from running
- Errors in on_tick_start and on_phase_complete don't stop tick execution

### ConsoleNarrator

Outputs narratives to stdout.

#### ConsoleNarrator.__init__(show_narratives: bool = True) -> None

Initialize console narrator.

- **Parameters**:
  - show_narratives — if True, print full narratives; if False, only header/footer

#### ConsoleNarrator.output(report: TickReport) -> None

Print narratives to stdout.

- **Input**: TickReport with narratives
- **Side effects**: prints to stdout (header/footer always, content if show_narratives=True)
- **Errors**: logged, never raised

**Behavior:**
- When `show_narratives=True` (default): full output with location names and narratives
- When `show_narratives=False`: only header and footer, no narrative content

#### ConsoleNarrator.on_tick_start(...) -> None

No-op implementation. Does nothing.

#### ConsoleNarrator.on_phase_complete(...) -> None

No-op implementation. Does nothing.

---

## Output Formats

### ConsoleNarrator

```
═══════════════════════════════════════════
TICK 42
═══════════════════════════════════════════

--- Tavern ---
The fire crackles softly as Bob enters the tavern. 
Elvira looks up from her drink, recognition flickering in her eyes.

--- Forest ---
Wind rustles through the ancient oaks. A distant wolf howls.

═══════════════════════════════════════════
```

**Format details:**
- Header with tick number (box-drawing characters)
- Each location separated by `--- Location Name ---`
- Empty line between locations
- Footer matches header

**Empty narratives:**
- Location with empty narrative — shown with `[No narrative]` marker
- All locations are always printed

### TelegramNarrator (Future - after MVP)

Sends narratives as Telegram messages.

---

## Error Handling

### Narrator Isolation

Each narrator runs independently. Failures are isolated:

```python
for narrator in narrators:
    try:
        narrator.output(report)
    except Exception as e:
        logger.error(f"Narrator {type(narrator).__name__} failed: {e}")
        # Continue to next narrator
```

### Console Errors

ConsoleNarrator may fail if stdout is closed (rare). Logged as warning.

### Network Errors (Future)

TelegramNarrator network failures:
- Logged as error
- Don't retry (tick already saved)
- User can re-read from TickLogger output

---

## Dependencies

- **Standard Library**: logging, sys, typing (Protocol)
- **External**: None
- **Internal**: runner (TickReport, PhaseData — via TYPE_CHECKING), utils.storage (Simulation — via TYPE_CHECKING)

---

## Usage Examples

### Basic Usage

```python
from datetime import datetime
from src.narrators import ConsoleNarrator
from src.runner import TickReport

narrator = ConsoleNarrator()
# Note: TickReport requires all fields, but narrators only use a subset
# In practice, TickRunner creates the complete TickReport
report = TickReport(
    sim_id="my-sim",
    tick_number=42,
    narratives={
        "tavern": "Bob enters the tavern.",
        "forest": "Wind rustles the trees.",
    },
    location_names={
        "tavern": "The Rusty Tankard",
        "forest": "Dark Forest",
    },
    success=True,
    timestamp=datetime.now(),
    duration=8.2,
    phases={},
    simulation=simulation,
    pending_memories={},
)

narrator.output(report)
```

### Quiet Mode (Header Only)

```python
# When using file logging, suppress console narratives
narrator = ConsoleNarrator(show_narratives=False)
narrator.output(report)  # Only shows tick header/footer
```

### Multiple Narrators

```python
from src.narrators import ConsoleNarrator

narrators = [
    ConsoleNarrator(),
    # TelegramNarrator(config),  # Future
]

for narrator in narrators:
    narrator.output(report)
```

### In TickRunner

```python
class TickRunner:
    def __init__(self, config, narrators: Sequence[Narrator]):
        self._narrators = narrators

    async def run_tick(self, sim_id: str) -> TickReport:
        # ... execute phases ...

        report = TickReport(...)  # Contains all data

        for narrator in self._narrators:
            try:
                narrator.output(report)
            except Exception as e:
                logger.error(f"Narrator failed: {e}")

        return report
```

---

## Test Coverage

### Unit Tests

- test_console_narrator_output — prints correct format
- test_console_narrator_empty_narratives — handles empty dict
- test_console_narrator_single_location — formats correctly
- test_console_narrator_multiple_locations — all locations printed
- test_narrator_protocol — ConsoleNarrator satisfies Protocol
- test_console_narrator_show_narratives_default_true — narratives shown by default
- test_console_narrator_show_narratives_false — header/footer only when show_narratives=False
- test_console_narrator_on_tick_start_noop — on_tick_start does nothing but doesn't raise
- test_console_narrator_on_phase_complete_noop — on_phase_complete does nothing but doesn't raise

### Integration Tests

- test_narrator_in_runner — narrator called after tick
- test_narrator_failure_isolated — one failure doesn't stop others

---

## Implementation Notes

### Protocol vs ABC

Using `typing.Protocol` for structural subtyping:
- No inheritance required
- Duck typing friendly
- Easy to mock in tests

```python
from typing import Protocol

class Narrator(Protocol):
    def output(self, report: TickReport) -> None: ...
```

### Box Drawing Characters

ConsoleNarrator uses Unicode box-drawing for visual separation:
- `═` (U+2550) — double horizontal line
- Works in most modern terminals
- Fallback: use `=` if encoding issues

### Encoding

ConsoleNarrator handles encoding issues for cross-platform compatibility:
- Attempts to reconfigure stdout for UTF-8 on Windows
- Uses `errors="replace"` fallback for unencodable characters
- Catches and logs encoding errors without failing
