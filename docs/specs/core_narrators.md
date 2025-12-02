# core_narrators.md

## Status: READY

Output handlers for Thing' Sandbox. Narrators receive tick results and deliver
narratives to various destinations: console, files, Telegram, web.

---

## Public API

### Narrator Protocol

Interface that all narrators must implement.

```python
class Narrator(Protocol):
    def output(self, result: TickResult) -> None:
        """Output tick result to destination."""
        ...
```

**Input:**
- result — TickResult from completed tick

**Side effects:**
- Writes to destination (stdout, file, network)

**Error handling:**
- Narrator errors are logged but don't affect tick success
- Failed narrator doesn't prevent other narrators from running

### ConsoleNarrator

Outputs narratives to stdout.

#### ConsoleNarrator.__init__() -> None

Initialize console narrator. No configuration required.

#### ConsoleNarrator.output(result: TickResult) -> None

Print narratives to stdout.

- **Input**: TickResult with narratives
- **Side effects**: prints to stdout
- **Errors**: logged, never raised

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

### FileNarrator (Future - B.5)

Writes to `logs/tick_NNNNNN.md` in simulation folder.

```markdown
# Tick 42

## Tavern

The fire crackles softly as Bob enters the tavern.
Elvira looks up from her drink, recognition flickering in her eyes.

## Forest

Wind rustles through the ancient oaks. A distant wolf howls.
```

### TelegramNarrator (Future - after MVP)

Sends narratives as Telegram messages.

---

## Error Handling

### Narrator Isolation

Each narrator runs independently. Failures are isolated:

```python
for narrator in narrators:
    try:
        narrator.output(result)
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
- User can re-read from file log

---

## Dependencies

- **Standard Library**: logging, sys, typing (Protocol)
- **External**: None
- **Internal**: runner (TickResult)

---

## Usage Examples

### Basic Usage

```python
from src.narrators import ConsoleNarrator
from src.runner import TickResult

narrator = ConsoleNarrator()
result = TickResult(
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
)

narrator.output(result)
```

### Multiple Narrators

```python
from src.narrators import ConsoleNarrator, FileNarrator

narrators = [
    ConsoleNarrator(),
    FileNarrator(sim_path),  # Future
]

for narrator in narrators:
    narrator.output(result)
```

### In TickRunner

```python
class TickRunner:
    def __init__(self, config, narrators: Sequence[Narrator]):
        self._narrators = narrators

    async def run_tick(self, sim_id: str) -> TickResult:
        # ... execute phases ...
        
        for narrator in self._narrators:
            try:
                narrator.output(result)
            except Exception as e:
                logger.error(f"Narrator failed: {e}")
        
        return result
```

---

## Test Coverage

### Unit Tests

- test_console_narrator_output — prints correct format
- test_console_narrator_empty_narratives — handles empty dict
- test_console_narrator_single_location — formats correctly
- test_console_narrator_multiple_locations — all locations printed
- test_narrator_protocol — ConsoleNarrator satisfies Protocol

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
    def output(self, result: TickResult) -> None: ...
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
