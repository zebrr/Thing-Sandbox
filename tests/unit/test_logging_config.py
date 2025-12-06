"""Unit tests for logging_config module."""

import logging

import pytest

from src.utils.logging_config import (
    DEFAULT_EMOJI,
    EMOJI_MAP,
    EmojiFormatter,
    setup_logging,
)


class TestEmojiMap:
    """Tests for emoji mapping constants."""

    def test_emoji_map_has_all_modules(self) -> None:
        """EMOJI_MAP contains entries for all documented modules."""
        expected_modules = [
            "config",
            "runner",
            "phase1",
            "phase2a",
            "phase2b",
            "phase3",
            "phase4",
            "llm",
            "openai",
            "storage",
            "prompts",
            "narrators",
        ]
        for module in expected_modules:
            assert module in EMOJI_MAP, f"Missing emoji for module: {module}"

    def test_default_emoji_is_defined(self) -> None:
        """DEFAULT_EMOJI is a non-empty string."""
        assert DEFAULT_EMOJI
        assert isinstance(DEFAULT_EMOJI, str)


class TestEmojiFormatter:
    """Tests for EmojiFormatter class."""

    def test_format_includes_timestamp(self) -> None:
        """Formatted output includes timestamp in correct format."""
        formatter = EmojiFormatter()
        record = logging.LogRecord(
            name="src.config",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Check timestamp format: YYYY.MM.DD HH:MM:SS
        assert result[4] == "."  # Year-month separator
        assert result[7] == "."  # Month-day separator
        assert result[10] == " "  # Date-time separator
        assert result[13] == ":"  # Hour-minute separator
        assert result[16] == ":"  # Minute-second separator

    def test_format_includes_level_padded(self) -> None:
        """Level name is padded to 7 characters."""
        formatter = EmojiFormatter()
        record = logging.LogRecord(
            name="src.config",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # INFO should be padded: "INFO   "
        assert "| INFO    |" in result

    def test_format_includes_emoji_for_known_module(self) -> None:
        """Emoji is included for known modules."""
        formatter = EmojiFormatter()
        record = logging.LogRecord(
            name="src.phases.phase1",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert EMOJI_MAP["phase1"] in result

    def test_format_uses_default_emoji_for_unknown_module(self) -> None:
        """Default emoji is used for unknown modules."""
        formatter = EmojiFormatter()
        record = logging.LogRecord(
            name="src.unknown.module",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert DEFAULT_EMOJI in result

    def test_format_extracts_short_module_name(self) -> None:
        """Short module name is extracted from full path."""
        formatter = EmojiFormatter()
        record = logging.LogRecord(
            name="src.phases.phase1",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "phase1:" in result
        assert "src.phases.phase1" not in result

    def test_format_includes_message(self) -> None:
        """Message content is included in output."""
        formatter = EmojiFormatter()
        record = logging.LogRecord(
            name="src.config",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Configuration loaded successfully",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Configuration loaded successfully" in result

    def test_format_handles_message_with_args(self) -> None:
        """Message with format args is formatted correctly."""
        formatter = EmojiFormatter()
        record = logging.LogRecord(
            name="src.config",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Loaded %d items from %s",
            args=(42, "file.json"),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Loaded 42 items from file.json" in result

    def test_format_different_levels(self) -> None:
        """Different log levels are formatted correctly."""
        formatter = EmojiFormatter()

        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
        ]

        for level, name in levels:
            record = logging.LogRecord(
                name="src.config",
                level=level,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None,
            )
            result = formatter.format(record)
            assert name in result

    def test_format_non_ascii_message(self) -> None:
        """Non-ASCII characters in message are preserved."""
        formatter = EmojiFormatter()
        record = logging.LogRecord(
            name="src.config",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Загружено из файла: 你好",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Загружено из файла: 你好" in result


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_configures_root_logger(self) -> None:
        """setup_logging adds handler to root logger."""
        # Clear existing handlers
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            setup_logging()

            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0], logging.StreamHandler)
            assert isinstance(root.handlers[0].formatter, EmojiFormatter)
        finally:
            # Restore original handlers
            root.handlers = original_handlers

    def test_setup_logging_sets_level(self) -> None:
        """setup_logging sets specified level."""
        root = logging.getLogger()
        original_level = root.level
        original_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            setup_logging(level=logging.DEBUG)

            assert root.level == logging.DEBUG
        finally:
            root.level = original_level
            root.handlers = original_handlers

    def test_setup_logging_removes_existing_handlers(self) -> None:
        """setup_logging removes existing handlers to avoid duplicates."""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers.clear()

        # Add dummy handler
        dummy_handler = logging.StreamHandler()
        root.addHandler(dummy_handler)

        try:
            setup_logging()

            # Should have exactly 1 handler (not 2)
            assert len(root.handlers) == 1
            assert root.handlers[0] is not dummy_handler
        finally:
            root.handlers = original_handlers

    def test_setup_logging_default_level_is_info(self) -> None:
        """Default logging level is INFO."""
        root = logging.getLogger()
        original_level = root.level
        original_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            setup_logging()

            assert root.level == logging.INFO
        finally:
            root.level = original_level
            root.handlers = original_handlers

    def test_setup_logging_output_to_stderr(self) -> None:
        """Handler outputs to stderr."""
        import sys

        root = logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            setup_logging()

            handler = root.handlers[0]
            assert isinstance(handler, logging.StreamHandler)
            assert handler.stream is sys.stderr
        finally:
            root.handlers = original_handlers


class TestIntegration:
    """Integration tests for logging config."""

    def test_logged_message_has_correct_format(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Actual logged message follows expected format."""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        root.handlers.clear()

        try:
            setup_logging(level=logging.INFO)

            logger = logging.getLogger("src.phases.phase1")
            logger.info("Processing character: bob")

            captured = capfd.readouterr()
            # Output goes to stderr
            output = captured.err

            # Verify format components
            assert "|" in output  # Separators
            assert "🎭" in output  # Phase1 emoji
            assert "phase1:" in output  # Module name
            assert "Processing character: bob" in output  # Message
            assert "INFO" in output  # Level
        finally:
            root.handlers = original_handlers
            root.level = original_level
