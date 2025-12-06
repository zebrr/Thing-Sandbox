"""Logging configuration for Thing' Sandbox.

Provides unified logging format with emoji prefixes for module identification.
Configure logging once at CLI startup.

Example:
    >>> from src.utils.logging_config import setup_logging
    >>> import logging
    >>> setup_logging(level=logging.DEBUG)
    >>> logger = logging.getLogger("src.phases.phase1")
    >>> logger.info("Processing characters")
    2025.06.05 14:32:07 | INFO    | 🎭 phase1: Processing characters
"""

import logging
import sys
from datetime import datetime

# Module emoji mapping
EMOJI_MAP: dict[str, str] = {
    "config": "⚙️",
    "runner": "🎬",
    "phase1": "🎭",
    "phase2a": "⚖️",
    "phase2b": "📖",
    "phase3": "🔧",
    "phase4": "🧠",
    "llm": "🤖",
    "openai": "🤖",
    "storage": "💾",
    "prompts": "📝",
    "narrators": "📢",
}

DEFAULT_EMOJI = "📋"


class EmojiFormatter(logging.Formatter):
    """Custom formatter with emoji prefixes and unified timestamp format.

    Format: YYYY.MM.DD HH:MM:SS | LEVEL   | 🏷️ module: message

    Example:
        >>> formatter = EmojiFormatter()
        >>> handler = logging.StreamHandler()
        >>> handler.setFormatter(formatter)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with emoji prefix.

        Args:
            record: Log record to format.

        Returns:
            Formatted log string.
        """
        # Extract short module name from record.name
        # e.g., "src.phases.phase1" → "phase1"
        # e.g., "src.utils.llm_adapters.openai" → "openai"
        module = record.name.rsplit(".", 1)[-1]

        # Handle llm_adapters prefix
        if module.startswith("llm_adapters"):
            module = "openai"

        emoji = EMOJI_MAP.get(module, DEFAULT_EMOJI)

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y.%m.%d %H:%M:%S")

        # Pad level to 7 characters
        level = record.levelname.ljust(7)

        # Build formatted message
        return f"{timestamp} | {level} | {emoji} {module}: {record.getMessage()}"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with emoji formatter.

    Sets up a StreamHandler with EmojiFormatter on the root logger.
    Removes existing handlers to avoid duplicate output.

    Args:
        level: Logging level (default: logging.INFO).

    Example:
        >>> import logging
        >>> setup_logging(level=logging.DEBUG)
        >>> logging.getLogger("src.config").info("Config loaded")
        2025.06.05 14:32:07 | INFO    | ⚙️ config: Config loaded
    """
    root_logger = logging.getLogger()

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler with emoji formatter
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(EmojiFormatter())

    # Configure root logger
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
