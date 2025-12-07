"""Unit tests for narrators module."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest

from src.narrators import BOX_CHAR, HEADER_WIDTH, ConsoleNarrator, Narrator


@dataclass
class MockTickResult:
    """Mock TickResult for testing narrators without importing runner."""

    sim_id: str
    tick_number: int
    narratives: dict[str, str]
    location_names: dict[str, str]
    success: bool
    error: str | None = None


class TestNarratorProtocol:
    """Tests for Narrator protocol compliance."""

    def test_console_narrator_satisfies_protocol(self) -> None:
        """ConsoleNarrator satisfies Narrator protocol."""
        narrator: Narrator = ConsoleNarrator()

        # Protocol requires output method
        assert hasattr(narrator, "output")
        assert callable(narrator.output)

    def test_custom_narrator_satisfies_protocol(self) -> None:
        """Custom class with output method satisfies Narrator protocol."""

        class CustomNarrator:
            def output(self, result: MockTickResult) -> None:
                pass

        narrator: Narrator = CustomNarrator()  # type: ignore[assignment]
        assert hasattr(narrator, "output")


class TestConsoleNarrator:
    """Tests for ConsoleNarrator class."""

    def test_console_narrator_init(self) -> None:
        """ConsoleNarrator initializes without arguments."""
        narrator = ConsoleNarrator()
        assert narrator is not None

    def test_console_narrator_output_single_location(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator outputs single location correctly."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=42,
            narratives={"tavern": "Bob enters the tavern."},
            location_names={"tavern": "The Rusty Tankard"},
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Check header
        assert "test-sim - tick #42" in output
        assert BOX_CHAR in output

        # Check location
        assert "----- The Rusty Tankard (tavern) -----" in output
        assert "Bob enters the tavern." in output

    def test_console_narrator_output_multiple_locations(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """ConsoleNarrator outputs all locations."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=1,
            narratives={
                "tavern": "Fire crackles.",
                "forest": "Wind howls.",
            },
            location_names={
                "tavern": "Tavern",
                "forest": "Dark Forest",
            },
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        assert "----- Tavern (tavern) -----" in output
        assert "Fire crackles." in output
        assert "----- Dark Forest (forest) -----" in output
        assert "Wind howls." in output

    def test_console_narrator_empty_narrative(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator shows [No narrative] for empty string."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=5,
            narratives={"tavern": ""},
            location_names={"tavern": "Tavern"},
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        assert "[No narrative]" in output

    def test_console_narrator_whitespace_only_narrative(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """ConsoleNarrator shows [No narrative] for whitespace-only string."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=5,
            narratives={"tavern": "   \n\t  "},
            location_names={"tavern": "Tavern"},
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        assert "[No narrative]" in output

    def test_console_narrator_empty_narratives_dict(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator handles empty narratives dict."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=0,
            narratives={},
            location_names={},
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Should still have header and footer
        assert "test-sim - tick #0" in output
        assert BOX_CHAR in output

    def test_console_narrator_missing_location_name(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator falls back to location_id if name missing."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=1,
            narratives={"unknown_loc": "Something happens."},
            location_names={},  # No names provided
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Should use location_id as fallback
        assert "----- unknown_loc (unknown_loc) -----" in output
        assert "Something happens." in output

    def test_console_narrator_non_ascii_content(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator handles non-ASCII characters."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=1,
            narratives={"tavern": "Боб входит в таверну. 你好世界"},
            location_names={"tavern": "Таверна «Ржавая Кружка»"},
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        assert "Таверна «Ржавая Кружка»" in output
        assert "Боб входит в таверну." in output
        assert "你好世界" in output

    def test_console_narrator_header_width(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator header line has correct width."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=1,
            narratives={},
            location_names={},
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        lines = captured.out.split("\n")

        # First non-empty line should be the header
        non_empty_lines = [line for line in lines if line.strip()]
        header_line = non_empty_lines[0]
        assert len(header_line) == HEADER_WIDTH
        assert all(c == BOX_CHAR for c in header_line)

    def test_console_narrator_catches_exceptions(self) -> None:
        """ConsoleNarrator catches and logs exceptions without raising."""
        narrator = ConsoleNarrator()
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=1,
            narratives={"loc": "text"},
            location_names={"loc": "Location"},
            success=True,
        )

        # Mock print to raise exception
        with patch("builtins.print", side_effect=OSError("stdout closed")):
            # Should not raise
            narrator.output(result)  # type: ignore[arg-type]

    def test_console_narrator_show_narratives_default_true(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """ConsoleNarrator shows narratives by default."""
        narrator = ConsoleNarrator()  # Default show_narratives=True
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=42,
            narratives={"tavern": "Bob enters the tavern."},
            location_names={"tavern": "The Rusty Tankard"},
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Should include narrative content
        assert "----- The Rusty Tankard (tavern) -----" in output
        assert "Bob enters the tavern." in output

    def test_console_narrator_show_narratives_false(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator hides narratives when show_narratives=False."""
        narrator = ConsoleNarrator(show_narratives=False)
        result = MockTickResult(
            sim_id="test-sim",
            tick_number=42,
            narratives={"tavern": "Bob enters the tavern."},
            location_names={"tavern": "The Rusty Tankard"},
            success=True,
        )

        narrator.output(result)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Should have header and footer
        assert "test-sim - tick #42" in output
        assert BOX_CHAR in output

        # Should NOT include narrative content
        assert "----- The Rusty Tankard (tavern) -----" not in output
        assert "Bob enters the tavern." not in output
        assert "[No narrative]" not in output
