"""Unit tests for narrators module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest

from src.narrators import BOX_CHAR, HEADER_WIDTH, ConsoleNarrator, Narrator


@dataclass
class MockPhaseData:
    """Mock PhaseData for testing narrators without importing runner."""

    duration: float = 0.0
    stats: Any = None
    data: Any = None


@dataclass
class MockSimulation:
    """Mock Simulation for testing narrators without importing storage."""

    id: str = "test-sim"
    current_tick: int = 0
    characters: dict[str, Any] = field(default_factory=dict)
    locations: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockTickReport:
    """Mock TickReport for testing narrators without importing runner."""

    sim_id: str
    tick_number: int
    narratives: dict[str, str]
    location_names: dict[str, str]
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0
    phases: dict[str, Any] = field(default_factory=dict)
    simulation: Any = None
    pending_memories: dict[str, str] = field(default_factory=dict)
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
        """Custom class with all protocol methods satisfies Narrator protocol."""

        class CustomNarrator:
            def output(self, report: MockTickReport) -> None:
                pass

            async def on_tick_start(
                self, sim_id: str, tick_number: int, simulation: MockSimulation
            ) -> None:
                pass

            async def on_phase_complete(self, phase_name: str, phase_data: MockPhaseData) -> None:
                pass

        narrator: Narrator = CustomNarrator()  # type: ignore[assignment]
        assert hasattr(narrator, "output")
        assert hasattr(narrator, "on_tick_start")
        assert hasattr(narrator, "on_phase_complete")


class TestConsoleNarrator:
    """Tests for ConsoleNarrator class."""

    def test_console_narrator_init(self) -> None:
        """ConsoleNarrator initializes without arguments."""
        narrator = ConsoleNarrator()
        assert narrator is not None

    def test_console_narrator_output_single_location(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator outputs single location correctly."""
        narrator = ConsoleNarrator()
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=42,
            narratives={"tavern": "Bob enters the tavern."},
            location_names={"tavern": "The Rusty Tankard"},
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

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
        report = MockTickReport(
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

        narrator.output(report)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        assert "----- Tavern (tavern) -----" in output
        assert "Fire crackles." in output
        assert "----- Dark Forest (forest) -----" in output
        assert "Wind howls." in output

    def test_console_narrator_empty_narrative(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator shows [No narrative] for empty string."""
        narrator = ConsoleNarrator()
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=5,
            narratives={"tavern": ""},
            location_names={"tavern": "Tavern"},
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        assert "[No narrative]" in output

    def test_console_narrator_whitespace_only_narrative(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """ConsoleNarrator shows [No narrative] for whitespace-only string."""
        narrator = ConsoleNarrator()
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=5,
            narratives={"tavern": "   \n\t  "},
            location_names={"tavern": "Tavern"},
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        assert "[No narrative]" in output

    def test_console_narrator_empty_narratives_dict(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator handles empty narratives dict."""
        narrator = ConsoleNarrator()
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=0,
            narratives={},
            location_names={},
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Should still have header and footer
        assert "test-sim - tick #0" in output
        assert BOX_CHAR in output

    def test_console_narrator_missing_location_name(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator falls back to location_id if name missing."""
        narrator = ConsoleNarrator()
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={"unknown_loc": "Something happens."},
            location_names={},  # No names provided
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Should use location_id as fallback
        assert "----- unknown_loc (unknown_loc) -----" in output
        assert "Something happens." in output

    def test_console_narrator_non_ascii_content(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator handles non-ASCII characters."""
        narrator = ConsoleNarrator()
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={"tavern": "Боб входит в таверну. 你好世界"},
            location_names={"tavern": "Таверна «Ржавая Кружка»"},
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        assert "Таверна «Ржавая Кружка»" in output
        assert "Боб входит в таверну." in output
        assert "你好世界" in output

    def test_console_narrator_header_width(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator header line has correct width."""
        narrator = ConsoleNarrator()
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={},
            location_names={},
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

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
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={"loc": "text"},
            location_names={"loc": "Location"},
            success=True,
        )

        # Mock print to raise exception
        with patch("builtins.print", side_effect=OSError("stdout closed")):
            # Should not raise
            narrator.output(report)  # type: ignore[arg-type]

    def test_console_narrator_show_narratives_default_true(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """ConsoleNarrator shows narratives by default."""
        narrator = ConsoleNarrator()  # Default show_narratives=True
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=42,
            narratives={"tavern": "Bob enters the tavern."},
            location_names={"tavern": "The Rusty Tankard"},
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Should include narrative content
        assert "----- The Rusty Tankard (tavern) -----" in output
        assert "Bob enters the tavern." in output

    def test_console_narrator_show_narratives_false(self, capsys: pytest.CaptureFixture) -> None:
        """ConsoleNarrator outputs nothing when show_narratives=False."""
        narrator = ConsoleNarrator(show_narratives=False)
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=42,
            narratives={"tavern": "Bob enters the tavern."},
            location_names={"tavern": "The Rusty Tankard"},
            success=True,
        )

        narrator.output(report)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        output = captured.out

        # Should output nothing at all
        assert output == ""

    @pytest.mark.asyncio
    async def test_console_narrator_on_tick_start_noop(self) -> None:
        """on_tick_start does nothing but doesn't raise."""
        narrator = ConsoleNarrator()
        simulation = MockSimulation()
        # Should not raise
        await narrator.on_tick_start("test-sim", 42, simulation)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_console_narrator_on_phase_complete_noop(self) -> None:
        """on_phase_complete does nothing but doesn't raise."""
        narrator = ConsoleNarrator()
        phase_data = MockPhaseData(duration=1.0, stats=None, data={})
        # Should not raise
        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]


# --- escape_html tests ---


class TestEscapeHtml:
    """Tests for escape_html function."""

    def test_escape_html_ampersand(self) -> None:
        """Ampersand is escaped to &amp;"""
        from src.narrators import escape_html

        assert escape_html("Tom & Jerry") == "Tom &amp; Jerry"

    def test_escape_html_less_than(self) -> None:
        """Less than is escaped to &lt;"""
        from src.narrators import escape_html

        assert escape_html("a < b") == "a &lt; b"

    def test_escape_html_greater_than(self) -> None:
        """Greater than is escaped to &gt;"""
        from src.narrators import escape_html

        assert escape_html("a > b") == "a &gt; b"

    def test_escape_html_combined(self) -> None:
        """All special chars escaped in combination."""
        from src.narrators import escape_html

        assert escape_html("<b>&</b>") == "&lt;b&gt;&amp;&lt;/b&gt;"

    def test_escape_html_no_change(self) -> None:
        """Regular text without special chars passes through unchanged."""
        from src.narrators import escape_html

        text = "Hello World! Привет мир 你好"
        assert escape_html(text) == text


# --- TelegramNarrator tests ---


@dataclass
class MockBatchStats:
    """Mock BatchStats for testing."""

    total_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0


@dataclass
class MockIntentionResponse:
    """Mock IntentionResponse for testing."""

    intention: str


@dataclass
class MockNarrativeResponse:
    """Mock NarrativeResponse for testing."""

    narrative: str


@dataclass
class MockCharacter:
    """Mock Character with identity."""

    identity: Any


@dataclass
class MockLocation:
    """Mock Location with identity."""

    identity: Any


@dataclass
class MockIdentity:
    """Mock Identity with name."""

    id: str
    name: str


class MockTelegramClient:
    """Mock TelegramClient for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        self.messages: list[tuple[str, str, int | None]] = []
        self.should_fail = should_fail

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        message_thread_id: int | None = None,
    ) -> bool:
        if self.should_fail:
            return False
        self.messages.append((chat_id, text, message_thread_id))
        return True


class TestTelegramNarrator:
    """Tests for TelegramNarrator class."""

    def _make_narrator(
        self,
        client: MockTelegramClient | None = None,
        mode: str = "full_stats",
        group_intentions: bool = True,
        group_narratives: bool = True,
        message_thread_id: int | None = None,
    ) -> Any:
        """Helper to create TelegramNarrator with mock client."""
        from src.narrators import TelegramNarrator

        if client is None:
            client = MockTelegramClient()
        return TelegramNarrator(
            client=client,  # type: ignore[arg-type]
            chat_id="-1001234567890",
            mode=mode,
            group_intentions=group_intentions,
            group_narratives=group_narratives,
            message_thread_id=message_thread_id,
        )

    def _make_simulation(self) -> MockSimulation:
        """Helper to create simulation with characters and locations."""
        sim = MockSimulation(id="test-sim", current_tick=41)
        sim.characters = {
            "bob": MockCharacter(identity=MockIdentity(id="bob", name="Bob the Builder")),
            "alice": MockCharacter(identity=MockIdentity(id="alice", name="Alice")),
        }
        sim.locations = {
            "tavern": MockLocation(identity=MockIdentity(id="tavern", name="The Rusty Tankard")),
            "forest": MockLocation(identity=MockIdentity(id="forest", name="Dark Forest")),
        }
        return sim

    def test_telegram_narrator_protocol(self) -> None:
        """TelegramNarrator satisfies Narrator protocol."""
        narrator = self._make_narrator()

        assert hasattr(narrator, "output")
        assert hasattr(narrator, "on_tick_start")
        assert hasattr(narrator, "on_phase_complete")

    @pytest.mark.asyncio
    async def test_on_tick_start_stores_simulation(self) -> None:
        """on_tick_start stores simulation reference."""
        narrator = self._make_narrator()
        simulation = self._make_simulation()

        await narrator.on_tick_start("test-sim", 42, simulation)  # type: ignore[arg-type]

        assert narrator._simulation is simulation
        assert narrator._sim_id == "test-sim"
        assert narrator._tick_number == 42

    @pytest.mark.asyncio
    async def test_on_tick_start_resets_phase2a_stats(self) -> None:
        """on_tick_start resets phase2a accumulator."""
        narrator = self._make_narrator()
        narrator._phase2a_stats = MockBatchStats(total_tokens=100)
        narrator._phase2a_duration = 5.0

        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        assert narrator._phase2a_stats is None
        assert narrator._phase2a_duration == 0.0

    @pytest.mark.asyncio
    async def test_on_phase_complete_phase1_sends_intentions(self) -> None:
        """phase1 triggers intention sending for mode=full."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, mode="full")
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {
            "bob": MockIntentionResponse(intention="I will build something"),
        }
        phase_data = MockPhaseData(
            duration=2.1,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )

        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 1
        assert "I will build something" in client.messages[0][1]
        assert "Bob the Builder" in client.messages[0][1]

    @pytest.mark.asyncio
    async def test_on_phase_complete_phase1_skipped_for_narratives_mode(self) -> None:
        """phase1 does not send intentions for mode=narratives."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, mode="narratives")
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {"bob": MockIntentionResponse(intention="Test intention")}
        phase_data = MockPhaseData(duration=2.1, stats=MockBatchStats(), data=intentions)

        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 0

    @pytest.mark.asyncio
    async def test_on_phase_complete_phase2a_stores_stats(self) -> None:
        """phase2a stores stats for later combination."""
        narrator = self._make_narrator()
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        stats = MockBatchStats(total_tokens=2000, reasoning_tokens=800)
        phase_data = MockPhaseData(duration=3.5, stats=stats, data={})

        await narrator.on_phase_complete("phase2a", phase_data)  # type: ignore[arg-type]

        assert narrator._phase2a_stats is stats
        assert narrator._phase2a_duration == 3.5

    @pytest.mark.asyncio
    async def test_on_phase_complete_phase2b_sends_narratives(self) -> None:
        """phase2b triggers narrative sending."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, mode="narratives")
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        narratives = {
            "tavern": MockNarrativeResponse(narrative="The fire crackles."),
        }
        phase_data = MockPhaseData(
            duration=4.0,
            stats=MockBatchStats(total_tokens=3000, reasoning_tokens=1000),
            data=narratives,
        )

        await narrator.on_phase_complete("phase2b", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 1
        assert "The fire crackles." in client.messages[0][1]
        assert "The Rusty Tankard" in client.messages[0][1]

    @pytest.mark.asyncio
    async def test_intentions_grouped_single_message(self) -> None:
        """Grouped intentions send single message."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, group_intentions=True)
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {
            "bob": MockIntentionResponse(intention="Build"),
            "alice": MockIntentionResponse(intention="Explore"),
        }
        phase_data = MockPhaseData(
            duration=2.0,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )

        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 1
        msg = client.messages[0][1]
        assert "Intentions" in msg
        assert "Build" in msg
        assert "Explore" in msg

    @pytest.mark.asyncio
    async def test_intentions_per_character_multiple_messages(self) -> None:
        """Per-character intentions send multiple messages."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, group_intentions=False)
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {
            "bob": MockIntentionResponse(intention="Build"),
            "alice": MockIntentionResponse(intention="Explore"),
        }
        phase_data = MockPhaseData(
            duration=2.0,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )

        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 2

    @pytest.mark.asyncio
    async def test_narratives_grouped_single_message(self) -> None:
        """Grouped narratives send single message."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, group_narratives=True, mode="narratives")
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        narratives = {
            "tavern": MockNarrativeResponse(narrative="Fire crackles."),
            "forest": MockNarrativeResponse(narrative="Wind howls."),
        }
        phase_data = MockPhaseData(
            duration=4.0,
            stats=MockBatchStats(total_tokens=3000, reasoning_tokens=1000),
            data=narratives,
        )

        await narrator.on_phase_complete("phase2b", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 1
        msg = client.messages[0][1]
        assert "Fire crackles." in msg
        assert "Wind howls." in msg

    @pytest.mark.asyncio
    async def test_narratives_per_location_multiple_messages(self) -> None:
        """Per-location narratives send multiple messages."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, group_narratives=False, mode="narratives")
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        narratives = {
            "tavern": MockNarrativeResponse(narrative="Fire crackles."),
            "forest": MockNarrativeResponse(narrative="Wind howls."),
        }
        phase_data = MockPhaseData(
            duration=4.0,
            stats=MockBatchStats(total_tokens=3000, reasoning_tokens=1000),
            data=narratives,
        )

        await narrator.on_phase_complete("phase2b", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 2

    @pytest.mark.asyncio
    async def test_stats_footer_only_for_stats_modes(self) -> None:
        """Stats footer appears only for _stats modes."""
        # Test full_stats shows footer
        client_stats = MockTelegramClient()
        narrator_stats = self._make_narrator(client=client_stats, mode="full_stats")
        await narrator_stats.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {"bob": MockIntentionResponse(intention="Build")}
        phase_data = MockPhaseData(
            duration=2.0,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )
        await narrator_stats.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert "📊" in client_stats.messages[0][1]
        assert "1,000 tok" in client_stats.messages[0][1]

        # Test full does NOT show footer
        client_no_stats = MockTelegramClient()
        narrator_no_stats = self._make_narrator(client=client_no_stats, mode="full")
        await narrator_no_stats.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        await narrator_no_stats.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert "📊" not in client_no_stats.messages[0][1]

    @pytest.mark.asyncio
    async def test_stats_footer_only_on_last_message(self) -> None:
        """Stats footer appears only on last message in per-item mode."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, mode="full_stats", group_intentions=False)
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {
            "bob": MockIntentionResponse(intention="Build"),
            "alice": MockIntentionResponse(intention="Explore"),
        }
        phase_data = MockPhaseData(
            duration=2.0,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )

        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        # First message should NOT have footer
        assert "📊" not in client.messages[0][1]
        # Last message SHOULD have footer
        assert "📊" in client.messages[1][1]

    @pytest.mark.asyncio
    async def test_phase2_stats_combined(self) -> None:
        """Phase 2 stats combine phase2a and phase2b."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, mode="narratives_stats")
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        # Phase 2a
        phase2a_data = MockPhaseData(
            duration=3.0,
            stats=MockBatchStats(total_tokens=2000, reasoning_tokens=800),
            data={},
        )
        await narrator.on_phase_complete("phase2a", phase2a_data)  # type: ignore[arg-type]

        # Phase 2b
        narratives = {"tavern": MockNarrativeResponse(narrative="Fire crackles.")}
        phase2b_data = MockPhaseData(
            duration=4.0,
            stats=MockBatchStats(total_tokens=3000, reasoning_tokens=1200),
            data=narratives,
        )
        await narrator.on_phase_complete("phase2b", phase2b_data)  # type: ignore[arg-type]

        msg = client.messages[0][1]
        # Combined: 2000+3000=5000 tokens, 800+1200=2000 reasoning, 3.0+4.0=7.0s
        assert "5,000 tok" in msg
        assert "2,000 reason" in msg
        assert "7.0s" in msg

    def test_output_is_noop(self) -> None:
        """output() does nothing."""
        narrator = self._make_narrator()
        report = MockTickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={},
            location_names={},
            success=True,
        )
        # Should not raise
        narrator.output(report)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_error_handling_continues(self) -> None:
        """Client errors don't stop processing."""
        client = MockTelegramClient(should_fail=True)
        narrator = self._make_narrator(client=client, mode="full", group_intentions=False)
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {
            "bob": MockIntentionResponse(intention="Build"),
            "alice": MockIntentionResponse(intention="Explore"),
        }
        phase_data = MockPhaseData(
            duration=2.0,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )

        # Should not raise despite client failure
        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_missing_simulation_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Missing simulation logs warning and skips."""
        narrator = self._make_narrator()
        # Don't call on_tick_start - simulation will be None

        intentions = {"bob": MockIntentionResponse(intention="Build")}
        phase_data = MockPhaseData(
            duration=2.0,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )

        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert "simulation is None" in caplog.text

    @pytest.mark.asyncio
    async def test_message_thread_id_passed_to_client(self) -> None:
        """message_thread_id is passed to send_message calls."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, mode="full", message_thread_id=42)
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {"bob": MockIntentionResponse(intention="Build")}
        phase_data = MockPhaseData(
            duration=2.0,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )

        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 1
        # Check message_thread_id is in the tuple
        assert client.messages[0][2] == 42

    @pytest.mark.asyncio
    async def test_message_thread_id_none_passed_to_client(self) -> None:
        """message_thread_id=None is passed when not set."""
        client = MockTelegramClient()
        narrator = self._make_narrator(client=client, mode="full")  # No thread_id
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        intentions = {"bob": MockIntentionResponse(intention="Build")}
        phase_data = MockPhaseData(
            duration=2.0,
            stats=MockBatchStats(total_tokens=1000, reasoning_tokens=500),
            data=intentions,
        )

        await narrator.on_phase_complete("phase1", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 1
        # Check message_thread_id is None
        assert client.messages[0][2] is None

    @pytest.mark.asyncio
    async def test_narratives_pass_thread_id(self) -> None:
        """message_thread_id is passed for narrative messages too."""
        client = MockTelegramClient()
        narrator = self._make_narrator(
            client=client, mode="narratives", message_thread_id=99
        )
        await narrator.on_tick_start("test-sim", 42, self._make_simulation())  # type: ignore[arg-type]

        narratives = {"tavern": MockNarrativeResponse(narrative="Fire crackles.")}
        phase_data = MockPhaseData(
            duration=4.0,
            stats=MockBatchStats(total_tokens=3000, reasoning_tokens=1000),
            data=narratives,
        )

        await narrator.on_phase_complete("phase2b", phase_data)  # type: ignore[arg-type]

        assert len(client.messages) == 1
        assert client.messages[0][2] == 99
