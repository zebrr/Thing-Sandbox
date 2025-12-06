# util_logging_config.md

## Module
`src/utils/logging_config.py`

## Purpose
Provides unified logging configuration with emoji prefixes for module identification.
Configures logging format, output destination, and log levels.

## Public API

### Constants

```python
EMOJI_MAP: dict[str, str]  # Module name → emoji mapping
DEFAULT_EMOJI: str         # Fallback emoji for unknown modules
```

### Classes

#### EmojiFormatter

Custom logging formatter with emoji prefixes and structured output.

```python
class EmojiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str: ...
```

**Output format:**
```
YYYY.MM.DD HH:MM:SS | LEVEL   | 🏷️ module: message
```

**Module name extraction:**
- Full path: `src.phases.phase1` → short name: `phase1`
- Emoji lookup in EMOJI_MAP, DEFAULT_EMOJI if not found

### Functions

#### setup_logging

```python
def setup_logging(level: int = logging.INFO) -> None
```

Configure root logger with EmojiFormatter.

**Parameters:**
- `level`: Logging level (default: `logging.INFO`)

**Behavior:**
- Removes existing handlers to avoid duplicates
- Creates StreamHandler writing to stderr
- Sets EmojiFormatter on handler
- Configures root logger level

## Emoji Mapping

| Module | Emoji | Description |
|--------|-------|-------------|
| config | ⚙️ | Configuration loading |
| runner | 🎬 | Tick orchestration |
| phase1 | 🎭 | Character intentions |
| phase2a | ⚖️ | Scene arbitration |
| phase2b | 📖 | Narrative generation |
| phase3 | 🔧 | Result application |
| phase4 | 🧠 | Memory summarization |
| llm | 🤖 | LLM client |
| openai | 🤖 | OpenAI adapter |
| storage | 💾 | Simulation storage |
| prompts | 📝 | Prompt rendering |
| narrators | 📢 | Output handlers |
| (default) | 📋 | Unknown modules |

## Usage

### CLI Integration

```python
# src/cli.py
from src.utils.logging_config import setup_logging

@app.callback()
def main(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(level=level)
```

### Module Logging

```python
# Any module
import logging

logger = logging.getLogger(__name__)

logger.debug("Detailed info for debugging")
logger.info("Key operation completed")
logger.warning("Something unexpected but handled")
logger.error("Operation failed")
```

## Output Examples

```
2025.06.05 14:32:07 | INFO    | ⚙️ config: Loaded from config.toml
2025.06.05 14:32:07 | INFO    | 🎬 runner: Starting tick 1 for demo-sim
2025.06.05 14:32:08 | DEBUG   | 🎭 phase1: Processing 3 characters
2025.06.05 14:32:09 | WARNING | 🎭 phase1: bob fallback to idle (invalid location)
2025.06.05 14:32:10 | INFO    | 💾 storage: Saved simulation state
```

## Design Decisions

1. **Emoji prefixes**: Visual identification of log source without reading text
2. **Stderr output**: Separates logging from CLI output (stdout)
3. **Handler replacement**: Avoids duplicate log lines from multiple setup calls
4. **Short module names**: Improves readability in terminal
5. **7-char level padding**: Aligns columns for consistent formatting

## Testing

See `tests/unit/test_logging_config.py`:
- `TestEmojiMap`: Constant completeness
- `TestEmojiFormatter`: Format components and edge cases
- `TestSetupLogging`: Logger configuration
- `TestIntegration`: End-to-end format verification
