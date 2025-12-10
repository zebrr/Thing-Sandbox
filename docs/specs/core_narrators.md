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

    async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
        """Called when tick execution begins."""
        ...

    async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """Called after each phase completes successfully."""
        ...
```

#### Narrator.output(report: TickReport) -> None

Output tick report to destination.

- **Input**: report — TickReport from completed tick
- **Side effects**: Writes to destination (stdout, network)

#### Narrator.on_tick_start(sim_id: str, tick_number: int, simulation: Simulation) -> None

Called when tick execution begins (after status set to "running").
Async method, awaited directly by runner (fast, no network I/O expected).

- **Input**:
  - sim_id — Simulation identifier
  - tick_number — Tick number about to execute (current_tick + 1)
  - simulation — Simulation instance with characters and locations
- **Side effects**: Implementation-specific (e.g., storing simulation reference)
- **Note**: Default implementations should be no-op

#### Narrator.on_phase_complete(phase_name: str, phase_data: PhaseData) -> None

Called after each phase completes successfully.
Async method using fire-and-forget pattern: runner creates tasks but doesn't await
immediately. All tasks are awaited at end of tick with timeout (30s).

- **Input**:
  - phase_name — Name of completed phase (phase1, phase2a, phase2b, phase3, phase4)
  - phase_data — PhaseData with duration, stats, and phase output
- **Side effects**: Implementation-specific (e.g., progress display, Telegram messages)
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

### escape_html

Module-level helper function for HTML escaping.

```python
def escape_html(text: str) -> str
```

Escapes HTML special characters for Telegram HTML parse mode.

- **Input**: text — Raw text that may contain HTML special characters
- **Returns**: Text safe for Telegram HTML parse mode
- **Escapes**: `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`

### TelegramNarrator

Sends tick updates to Telegram channel via lifecycle methods.

```python
class TelegramNarrator:
    def __init__(
        self,
        client: TelegramClient,
        chat_id: str,
        mode: str,
        group_intentions: bool,
        group_narratives: bool,
        message_thread_id: int | None = None,
    ) -> None
```

#### TelegramNarrator.\_\_init\_\_(...) -> None

Initialize Telegram narrator.

- **Parameters**:
  - client — TelegramClient instance (from utils.telegram_client)
  - chat_id — Target chat/channel ID
  - mode — Output mode: `narratives`, `narratives_stats`, `full`, `full_stats`
  - group_intentions — Group all intentions in one message (True) or send per-character (False)
  - group_narratives — Group all narratives in one message (True) or send per-location (False)
  - message_thread_id — Forum topic ID for supergroups with topics enabled (default: None)

#### TelegramNarrator.on_tick_start(...) -> None

Store simulation reference for name lookups.

- **Input**: sim_id, tick_number, simulation
- **Side effects**: Stores simulation, resets phase2a stats accumulator

#### TelegramNarrator.on_phase_complete(...) -> None

Send messages after relevant phases.

- **Input**: phase_name, phase_data
- **Behavior**:
  - `phase1` + mode in (full, full_stats) → sends intentions
  - `phase2a` → stores stats for combined Phase 2 footer
  - `phase2b` → sends narratives with combined Phase 2 stats

#### TelegramNarrator.output(...) -> None

No-op. All messages sent in on_phase_complete.

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

### TelegramNarrator

Sends messages via Telegram Bot API using HTML formatting.

#### Intentions (mode=full/full_stats, grouped)

```html
🎯 <b>{sim_id} — tick #{tick_number} | Intentions</b>

<b>{char_name}:</b>
{intention}

<b>{char_name}:</b>
{intention}

───
📊 <i>Phase 1: {total_tokens:,} tok · {reasoning_tokens:,} reason · {duration:.1f}s</i>
```

#### Intentions (mode=full/full_stats, per-character)

N messages. Stats footer only on last:

```html
🎯 <b>{sim_id} — tick #{tick_number} | {char_name}</b>

{intention}
```

#### Narratives (all modes except none, grouped)

```html
📖 <b>{sim_id} — tick #{tick_number} | Narratives</b>

<b>{loc_name}</b>
{narrative}

<b>{loc_name}</b>
{narrative}

───
📊 <i>Phase 2: {total_tokens:,} tok · {reasoning_tokens:,} reason · {duration:.1f}s</i>
```

#### Narratives (per-location)

M messages. Stats footer only on last:

```html
📖 <b>{sim_id} — tick #{tick_number} | {loc_name}</b>

{narrative}
```

#### Stats Footer

- Shown only for `_stats` modes (narratives_stats, full_stats)
- Only on last message of each type
- For narratives: combined Phase 2a + Phase 2b stats
- Separator: `───` (U+2500 box drawing)

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

### Telegram Errors

TelegramNarrator error handling:
- TelegramClient errors → logged as WARNING, continue with next message
- Missing simulation (on_tick_start not called) → logged as WARNING, skip
- Lifecycle methods never raise exceptions (runner isolates anyway)
- After tick save, if Telegram times out → data safe on disk, logged as WARNING
- Individual message failures don't stop subsequent messages

---

## Dependencies

- **Standard Library**: logging, sys, typing (Protocol)
- **External**: None
- **Internal**:
  - runner (TickReport, PhaseData — via TYPE_CHECKING)
  - utils.storage (Simulation — via TYPE_CHECKING)
  - utils.llm (BatchStats)
  - utils.telegram_client (TelegramClient)

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
from src.narrators import ConsoleNarrator, TelegramNarrator
from src.utils.telegram_client import TelegramClient

client = TelegramClient(bot_token)
narrators = [
    ConsoleNarrator(),
    TelegramNarrator(
        client=client,
        chat_id="-1001234567890",
        mode="full_stats",
        group_intentions=True,
        group_narratives=True,
    ),
]

for narrator in narrators:
    narrator.output(report)
```

### TelegramNarrator Usage

```python
from src.narrators import TelegramNarrator
from src.utils.telegram_client import TelegramClient

# Create client (should be reused across ticks)
client = TelegramClient("123456:ABC-token")

# Create narrator
narrator = TelegramNarrator(
    client=client,
    chat_id="-1001234567890",
    mode="full_stats",          # narratives, narratives_stats, full, full_stats
    group_intentions=True,      # True: single message, False: per-character
    group_narratives=True,      # True: single message, False: per-location
    message_thread_id=42,       # Optional: forum topic ID for supergroups
)

# Used by runner via lifecycle methods:
# await narrator.on_tick_start(sim_id, tick_number, simulation)
# await narrator.on_phase_complete("phase1", phase_data)  # sends intentions
# await narrator.on_phase_complete("phase2a", phase_data)  # stores stats
# await narrator.on_phase_complete("phase2b", phase_data)  # sends narratives
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

### Unit Tests — escape_html

- test_escape_html_ampersand — `&` → `&amp;`
- test_escape_html_less_than — `<` → `&lt;`
- test_escape_html_greater_than — `>` → `&gt;`
- test_escape_html_combined — `<b>&</b>` → `&lt;b&gt;&amp;&lt;/b&gt;`
- test_escape_html_no_change — regular text unchanged

### Unit Tests — ConsoleNarrator

- test_console_narrator_output — prints correct format
- test_console_narrator_empty_narratives — handles empty dict
- test_console_narrator_single_location — formats correctly
- test_console_narrator_multiple_locations — all locations printed
- test_narrator_protocol — ConsoleNarrator satisfies Protocol
- test_console_narrator_show_narratives_default_true — narratives shown by default
- test_console_narrator_show_narratives_false — header/footer only when show_narratives=False
- test_console_narrator_on_tick_start_noop — on_tick_start does nothing but doesn't raise
- test_console_narrator_on_phase_complete_noop — on_phase_complete does nothing but doesn't raise

### Unit Tests — TelegramNarrator

- test_telegram_narrator_protocol — satisfies Narrator protocol
- test_on_tick_start_stores_simulation — simulation reference stored
- test_on_tick_start_resets_phase2a_stats — phase2a accumulator reset
- test_on_phase_complete_phase1_sends_intentions — intentions sent for mode=full
- test_on_phase_complete_phase1_skipped_for_narratives_mode — skipped for mode=narratives
- test_on_phase_complete_phase2a_stores_stats — stats stored for combination
- test_on_phase_complete_phase2b_sends_narratives — narratives sent
- test_intentions_grouped_single_message — grouped: 1 message
- test_intentions_per_character_multiple_messages — per-char: N messages
- test_narratives_grouped_single_message — grouped: 1 message
- test_narratives_per_location_multiple_messages — per-loc: M messages
- test_stats_footer_only_for_stats_modes — footer only for _stats modes
- test_stats_footer_only_on_last_message — footer on last message only
- test_phase2_stats_combined — phase2a + phase2b stats combined
- test_output_is_noop — output() does nothing
- test_error_handling_continues — client errors don't stop processing
- test_missing_simulation_logs_warning — warning if simulation is None
- test_message_thread_id_passed_to_client — message_thread_id passed to send_message
- test_message_thread_id_none_passed_to_client — None passed when not set
- test_narratives_pass_thread_id — message_thread_id passed for narratives

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
- Supports async methods for lifecycle hooks

```python
from typing import Protocol

class Narrator(Protocol):
    def output(self, report: TickReport) -> None: ...
    async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None: ...
    async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None: ...
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
