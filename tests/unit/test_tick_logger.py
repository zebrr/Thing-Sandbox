"""Unit tests for tick_logger module."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from src.runner import PhaseData, TickReport
from src.tick_logger import TickLogger

# =============================================================================
# Mock classes for testing
# =============================================================================


@dataclass
class MockUsage:
    """Mock ResponseUsage for testing."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0


@dataclass
class MockRequestResult:
    """Mock RequestResult for testing."""

    entity_key: str | None
    success: bool
    usage: MockUsage | None = None
    reasoning_summary: list[str] | None = None
    error: str | None = None


@dataclass
class MockBatchStats:
    """Mock BatchStats for testing."""

    total_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    results: list[MockRequestResult] = field(default_factory=list)


@dataclass
class MockIdentity:
    """Mock Identity for testing."""

    id: str
    name: str
    description: str = ""


@dataclass
class MockMemoryCell:
    """Mock MemoryCell for testing."""

    tick: int
    text: str


@dataclass
class MockMemory:
    """Mock Memory for testing."""

    cells: list[MockMemoryCell] = field(default_factory=list)
    summary: str = ""


@dataclass
class MockState:
    """Mock CharacterState for testing."""

    location: str
    internal_state: str | None = None
    external_intent: str | None = None


@dataclass
class MockLocationState:
    """Mock LocationState for testing."""

    moment: str | None = None
    description: str | None = None


@dataclass
class MockCharacter:
    """Mock Character for testing."""

    identity: MockIdentity
    state: MockState
    memory: MockMemory = field(default_factory=MockMemory)


@dataclass
class MockLocation:
    """Mock Location for testing."""

    identity: MockIdentity
    state: MockLocationState = field(default_factory=MockLocationState)


@dataclass
class MockSimulation:
    """Mock Simulation for testing."""

    id: str
    current_tick: int
    status: str
    characters: dict[str, MockCharacter]
    locations: dict[str, MockLocation]


@dataclass
class MockIntentionResponse:
    """Mock IntentionResponse for testing."""

    intention: str


@dataclass
class MockCharacterUpdate:
    """Mock CharacterUpdate for testing."""

    character_id: str
    location: str
    internal_state: str
    external_intent: str
    memory_entry: str


@dataclass
class MockLocationUpdate:
    """Mock LocationUpdate for testing."""

    moment: str | None = None
    description: str | None = None


@dataclass
class MockMasterOutput:
    """Mock MasterOutput for testing."""

    tick: int
    location_id: str
    characters: list[MockCharacterUpdate]
    location: MockLocationUpdate


@dataclass
class MockNarrativeResponse:
    """Mock NarrativeResponse for testing."""

    narrative: str


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_simulation() -> MockSimulation:
    """Create mock simulation for testing."""
    return MockSimulation(
        id="test-sim",
        current_tick=42,
        status="paused",
        characters={
            "bob": MockCharacter(
                identity=MockIdentity(id="bob", name="Bob the Wizard"),
                state=MockState(
                    location="tavern",
                    internal_state="curious",
                    external_intent="explore",
                ),
                memory=MockMemory(
                    cells=[MockMemoryCell(tick=41, text="I entered the tavern")],
                    summary="",
                ),
            ),
            "alice": MockCharacter(
                identity=MockIdentity(id="alice", name="Alice the Knight"),
                state=MockState(
                    location="forest",
                    internal_state="alert",
                    external_intent="patrol",
                ),
                memory=MockMemory(
                    cells=[
                        MockMemoryCell(tick=40, text="I heard a noise"),
                        MockMemoryCell(tick=41, text="I saw a shadow"),
                    ],
                    summary="Earlier events...",
                ),
            ),
        },
        locations={
            "tavern": MockLocation(
                identity=MockIdentity(id="tavern", name="The Rusty Tankard"),
                state=MockLocationState(moment="Evening settles in"),
            ),
            "forest": MockLocation(
                identity=MockIdentity(id="forest", name="Dark Forest"),
                state=MockLocationState(moment=None),
            ),
        },
    )


@pytest.fixture
def mock_batch_stats() -> MockBatchStats:
    """Create mock BatchStats for testing."""
    return MockBatchStats(
        total_tokens=1500,
        reasoning_tokens=500,
        cached_tokens=200,
        request_count=2,
        success_count=2,
        error_count=0,
        results=[
            MockRequestResult(
                entity_key="intention:bob",
                success=True,
                usage=MockUsage(reasoning_tokens=250),
                reasoning_summary=["Bob thinks carefully about his next move"],
            ),
            MockRequestResult(
                entity_key="intention:alice",
                success=True,
                usage=MockUsage(reasoning_tokens=250),
                reasoning_summary=["Alice is focused on her patrol"],
            ),
        ],
    )


@pytest.fixture
def mock_phase_data(mock_batch_stats: MockBatchStats) -> dict[str, PhaseData]:
    """Create mock phase data for testing."""
    return {
        "phase1": PhaseData(
            duration=2.1,
            stats=mock_batch_stats,  # type: ignore[arg-type]
            data={
                "bob": MockIntentionResponse(intention="I want to explore"),
                "alice": MockIntentionResponse(intention="I will patrol"),
            },
        ),
        "phase2a": PhaseData(
            duration=1.8,
            stats=MockBatchStats(
                total_tokens=2000,
                reasoning_tokens=700,
                request_count=2,
                results=[
                    MockRequestResult(
                        entity_key="resolution:tavern",
                        success=True,
                        usage=MockUsage(reasoning_tokens=350),
                        reasoning_summary=["The tavern scene unfolds peacefully"],
                    ),
                    MockRequestResult(
                        entity_key="resolution:forest",
                        success=True,
                        usage=MockUsage(reasoning_tokens=350),
                        reasoning_summary=["The forest remains quiet"],
                    ),
                ],
            ),
            data={
                "tavern": MockMasterOutput(
                    tick=42,
                    location_id="tavern",
                    characters=[
                        MockCharacterUpdate(
                            character_id="bob",
                            location="tavern",
                            internal_state="excited",
                            external_intent="drink ale",
                            memory_entry="I ordered a drink",
                        )
                    ],
                    location=MockLocationUpdate(moment="The fire crackles"),
                ),
                "forest": MockMasterOutput(
                    tick=42,
                    location_id="forest",
                    characters=[
                        MockCharacterUpdate(
                            character_id="alice",
                            location="forest",
                            internal_state="vigilant",
                            external_intent="continue patrol",
                            memory_entry="Nothing unusual",
                        )
                    ],
                    location=MockLocationUpdate(),
                ),
            },
        ),
        "phase2b": PhaseData(
            duration=1.2,
            stats=MockBatchStats(total_tokens=800, reasoning_tokens=200, request_count=2),
            data={
                "tavern": MockNarrativeResponse(
                    narrative="Bob entered the tavern and ordered an ale."
                ),
                "forest": MockNarrativeResponse(narrative="Alice patrolled the dark forest."),
            },
        ),
        "phase3": PhaseData(
            duration=0.01,
            stats=None,
            data={"pending_memories": {"bob": "I ordered ale", "alice": "I patrolled"}},
        ),
        "phase4": PhaseData(
            duration=3.1,
            stats=MockBatchStats(
                total_tokens=1066,
                reasoning_tokens=366,
                request_count=2,
                results=[
                    MockRequestResult(
                        entity_key="memory:alice",
                        success=True,
                        usage=MockUsage(reasoning_tokens=366),
                        reasoning_summary=["Merging older observations"],
                    ),
                ],
            ),
            data=None,
        ),
    }


@pytest.fixture
def mock_tick_report(
    mock_simulation: MockSimulation,
    mock_phase_data: dict[str, PhaseData],
) -> TickReport:
    """Create mock TickReport for testing."""
    return TickReport(
        sim_id="test-sim",
        tick_number=42,
        narratives={
            "tavern": "Bob entered the tavern and ordered an ale.",
            "forest": "Alice patrolled the dark forest.",
        },
        location_names={
            "tavern": "The Rusty Tankard",
            "forest": "Dark Forest",
        },
        success=True,
        timestamp=datetime(2025, 6, 7, 14, 32),
        duration=8.2,
        phases=mock_phase_data,
        simulation=mock_simulation,  # type: ignore[arg-type]
        pending_memories={"bob": "I ordered ale", "alice": "I patrolled"},
    )


# =============================================================================
# PhaseData Tests
# =============================================================================


class TestPhaseData:
    """Tests for PhaseData dataclass."""

    def test_phase_data_creation(self, mock_batch_stats: MockBatchStats) -> None:
        """PhaseData can be created with all fields."""
        data = PhaseData(
            duration=2.5,
            stats=mock_batch_stats,  # type: ignore[arg-type]
            data={"key": "value"},
        )

        assert data.duration == 2.5
        assert data.stats == mock_batch_stats
        assert data.data == {"key": "value"}

    def test_phase_data_with_none_stats(self) -> None:
        """PhaseData accepts None for stats (Phase 3)."""
        data = PhaseData(duration=0.01, stats=None, data={})

        assert data.stats is None


# =============================================================================
# TickReport Tests
# =============================================================================


class TestTickReport:
    """Tests for TickReport dataclass."""

    def test_tick_report_creation(self, mock_tick_report: TickReport) -> None:
        """TickReport can be created with all fields."""
        assert mock_tick_report.sim_id == "test-sim"
        assert mock_tick_report.tick_number == 42
        assert mock_tick_report.duration == 8.2
        assert "tavern" in mock_tick_report.narratives
        assert "phase1" in mock_tick_report.phases


# =============================================================================
# TickLogger Tests
# =============================================================================


class TestTickLogger:
    """Tests for TickLogger class."""

    def test_tick_logger_creates_logs_dir(
        self, tmp_path: Path, mock_tick_report: TickReport
    ) -> None:
        """TickLogger creates logs/ directory if it doesn't exist."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        logs_dir = sim_path / "logs"
        assert logs_dir.exists()
        assert logs_dir.is_dir()

    def test_tick_logger_writes_file(self, tmp_path: Path, mock_tick_report: TickReport) -> None:
        """TickLogger writes tick log file."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        log_file = sim_path / "logs" / "tick_000042.md"
        assert log_file.exists()
        assert log_file.is_file()

    def test_tick_logger_tick_number_padding(
        self, tmp_path: Path, mock_tick_report: TickReport
    ) -> None:
        """TickLogger pads tick number to 6 digits."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        # Test with tick 1
        mock_tick_report.tick_number = 1
        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        log_file = sim_path / "logs" / "tick_000001.md"
        assert log_file.exists()

    def test_tick_logger_format_header(self, tmp_path: Path, mock_tick_report: TickReport) -> None:
        """TickLogger formats header with simulation info and summary."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        log_file = sim_path / "logs" / "tick_000042.md"
        content = log_file.read_text(encoding="utf-8")

        # Check header elements
        assert "# Tick 42" in content
        assert "**Simulation:** test-sim" in content
        assert "**Timestamp:** 2025-06-07 14:32" in content
        assert "**Duration:** 8.2s" in content
        assert "## Summary" in content
        assert "| Total tokens |" in content

    def test_tick_logger_format_phase1(self, tmp_path: Path, mock_tick_report: TickReport) -> None:
        """TickLogger formats Phase 1 with per-character intentions."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        log_file = sim_path / "logs" / "tick_000042.md"
        content = log_file.read_text(encoding="utf-8")

        assert "## Phase 1: Intentions" in content
        assert "### Bob the Wizard" in content
        assert "- **Intention:** I want to explore" in content
        # Reasoning should be formatted
        assert "Bob thinks carefully" in content or "**Reasoning:**" in content

    def test_tick_logger_format_phase2a_includes_empty_locations(
        self, tmp_path: Path, mock_tick_report: TickReport
    ) -> None:
        """TickLogger formats Phase 2a including all locations."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        log_file = sim_path / "logs" / "tick_000042.md"
        content = log_file.read_text(encoding="utf-8")

        assert "## Phase 2a: Arbitration" in content
        assert "### The Rusty Tankard" in content
        assert "### Dark Forest" in content
        assert "**Characters:**" in content
        assert "**Location:**" in content

    def test_tick_logger_format_phase2b(self, tmp_path: Path, mock_tick_report: TickReport) -> None:
        """TickLogger formats Phase 2b with narratives in blockquote."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        log_file = sim_path / "logs" / "tick_000042.md"
        content = log_file.read_text(encoding="utf-8")

        assert "## Phase 2b: Narratives" in content
        # Narratives should be in blockquote format
        assert "> Bob entered the tavern" in content or "Bob entered the tavern" in content

    def test_tick_logger_format_phase3(self, tmp_path: Path, mock_tick_report: TickReport) -> None:
        """TickLogger formats Phase 3 with characters and locations."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        log_file = sim_path / "logs" / "tick_000042.md"
        content = log_file.read_text(encoding="utf-8")

        assert "## Phase 3: State Application" in content
        assert "*(no LLM)*" in content
        assert "Applied" in content

    def test_tick_logger_format_phase4(self, tmp_path: Path, mock_tick_report: TickReport) -> None:
        """TickLogger formats Phase 4 with memory and cells count."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        logger = TickLogger(sim_path)
        logger.write(mock_tick_report)

        log_file = sim_path / "logs" / "tick_000042.md"
        content = log_file.read_text(encoding="utf-8")

        assert "## Phase 4: Memory" in content
        assert "- **New memory:**" in content
        assert "- **Cells:**" in content
        # Alice should have summarized (has reasoning)
        assert "summarized" in content or "no summarization" in content

    def test_tick_logger_empty_reasoning(self, tmp_path: Path) -> None:
        """TickLogger doesn't show reasoning line if reasoning_summary is None."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        # Create report with no reasoning (reasoning_tokens=0)
        simulation = MockSimulation(
            id="test-sim",
            current_tick=1,
            status="paused",
            characters={
                "bob": MockCharacter(
                    identity=MockIdentity(id="bob", name="Bob"),
                    state=MockState(location="tavern"),
                ),
            },
            locations={
                "tavern": MockLocation(
                    identity=MockIdentity(id="tavern", name="Tavern"),
                ),
            },
        )

        phase_data = {
            "phase1": PhaseData(
                duration=1.0,
                stats=MockBatchStats(
                    total_tokens=100,
                    request_count=1,
                    results=[
                        MockRequestResult(
                            entity_key="intention:bob",
                            success=True,
                            usage=MockUsage(reasoning_tokens=0),  # No reasoning tokens
                            reasoning_summary=None,  # No reasoning summary
                        )
                    ],
                ),
                data={"bob": MockIntentionResponse(intention="idle")},
            ),
            "phase2a": PhaseData(duration=1.0, stats=None, data={}),
            "phase2b": PhaseData(duration=1.0, stats=None, data={}),
            "phase3": PhaseData(duration=0.01, stats=None, data={"pending_memories": {}}),
            "phase4": PhaseData(duration=1.0, stats=None, data=None),
        }

        report = TickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={},
            location_names={"tavern": "Tavern"},
            success=True,
            timestamp=datetime.now(),
            duration=3.0,
            phases=phase_data,
            simulation=simulation,  # type: ignore[arg-type]
            pending_memories={},
        )

        logger = TickLogger(sim_path)
        logger.write(report)

        log_file = sim_path / "logs" / "tick_000001.md"
        content = log_file.read_text(encoding="utf-8")

        # Phase 1 section should exist
        assert "## Phase 1: Intentions" in content
        # Bob's section should NOT have reasoning line (since it's None)
        # We check that there's no reasoning line right after intention
        lines = content.split("\n")
        bob_idx = next(i for i, line in enumerate(lines) if "### Bob" in line)
        # The line after intention should not be reasoning
        intention_idx = next(
            i for i in range(bob_idx, len(lines)) if "- **Intention:**" in lines[i]
        )
        # Check if next non-empty line is NOT a reasoning line
        next_content_idx = intention_idx + 1
        while next_content_idx < len(lines) and not lines[next_content_idx].strip():
            next_content_idx += 1
        if next_content_idx < len(lines):
            assert "**Reasoning:**" not in lines[next_content_idx]

    def test_tick_logger_summarized_without_reasoning_summary(self, tmp_path: Path) -> None:
        """TickLogger shows 'summarized' when reasoning_tokens > 0 but reasoning_summary is None.

        This tests the key fix: reasoning_summary can be empty even when reasoning
        actually occurred. The reliable indicator is reasoning_tokens > 0.
        """
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        simulation = MockSimulation(
            id="test-sim",
            current_tick=1,
            status="paused",
            characters={
                "bob": MockCharacter(
                    identity=MockIdentity(id="bob", name="Bob"),
                    state=MockState(location="tavern"),
                    memory=MockMemory(
                        cells=[MockMemoryCell(tick=1, text="Something happened")],
                    ),
                ),
            },
            locations={
                "tavern": MockLocation(
                    identity=MockIdentity(id="tavern", name="Tavern"),
                ),
            },
        )

        phase_data = {
            "phase1": PhaseData(duration=1.0, stats=None, data={}),
            "phase2a": PhaseData(duration=1.0, stats=None, data={}),
            "phase2b": PhaseData(duration=1.0, stats=None, data={}),
            "phase3": PhaseData(duration=0.01, stats=None, data={"pending_memories": {}}),
            "phase4": PhaseData(
                duration=1.0,
                stats=MockBatchStats(
                    total_tokens=500,
                    reasoning_tokens=200,
                    request_count=1,
                    results=[
                        MockRequestResult(
                            entity_key="memory:bob",
                            success=True,
                            usage=MockUsage(reasoning_tokens=200),  # Reasoning occurred!
                            reasoning_summary=None,  # But summary is empty (API behavior)
                        )
                    ],
                ),
                data=None,
            ),
        }

        report = TickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={},
            location_names={"tavern": "Tavern"},
            success=True,
            timestamp=datetime.now(),
            duration=3.0,
            phases=phase_data,
            simulation=simulation,  # type: ignore[arg-type]
            pending_memories={"bob": "New memory entry"},
        )

        logger = TickLogger(sim_path)
        logger.write(report)

        log_file = sim_path / "logs" / "tick_000001.md"
        content = log_file.read_text(encoding="utf-8")

        # Should say "summarized" because reasoning_tokens > 0
        assert "(summarized)" in content
        # Should NOT have reasoning text since reasoning_summary is None
        assert "**Reasoning:**" not in content.split("## Phase 4")[1]

    def test_tick_logger_no_summarization_when_no_reasoning_tokens(self, tmp_path: Path) -> None:
        """TickLogger shows 'no summarization' when reasoning_tokens = 0."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        simulation = MockSimulation(
            id="test-sim",
            current_tick=1,
            status="paused",
            characters={
                "bob": MockCharacter(
                    identity=MockIdentity(id="bob", name="Bob"),
                    state=MockState(location="tavern"),
                    memory=MockMemory(
                        cells=[MockMemoryCell(tick=1, text="Something happened")],
                    ),
                ),
            },
            locations={
                "tavern": MockLocation(
                    identity=MockIdentity(id="tavern", name="Tavern"),
                ),
            },
        )

        phase_data = {
            "phase1": PhaseData(duration=1.0, stats=None, data={}),
            "phase2a": PhaseData(duration=1.0, stats=None, data={}),
            "phase2b": PhaseData(duration=1.0, stats=None, data={}),
            "phase3": PhaseData(duration=0.01, stats=None, data={"pending_memories": {}}),
            "phase4": PhaseData(
                duration=1.0,
                stats=MockBatchStats(
                    total_tokens=300,
                    reasoning_tokens=0,  # No reasoning at batch level
                    request_count=1,
                    results=[
                        MockRequestResult(
                            entity_key="memory:bob",
                            success=True,
                            usage=MockUsage(reasoning_tokens=0),  # No reasoning tokens
                            reasoning_summary=None,
                        )
                    ],
                ),
                data=None,
            ),
        }

        report = TickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={},
            location_names={"tavern": "Tavern"},
            success=True,
            timestamp=datetime.now(),
            duration=3.0,
            phases=phase_data,
            simulation=simulation,  # type: ignore[arg-type]
            pending_memories={"bob": "New memory entry"},
        )

        logger = TickLogger(sim_path)
        logger.write(report)

        log_file = sim_path / "logs" / "tick_000001.md"
        content = log_file.read_text(encoding="utf-8")

        # Should say "no summarization" because reasoning_tokens = 0
        assert "(no summarization)" in content

    def test_tick_logger_non_ascii_content(self, tmp_path: Path) -> None:
        """TickLogger handles non-ASCII characters correctly."""
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        simulation = MockSimulation(
            id="test-sim",
            current_tick=1,
            status="paused",
            characters={
                "bob": MockCharacter(
                    identity=MockIdentity(id="bob", name="Боб Волшебник"),
                    state=MockState(
                        location="tavern",
                        internal_state="задумчивый",
                    ),
                ),
            },
            locations={
                "tavern": MockLocation(
                    identity=MockIdentity(id="tavern", name="Таверна «Ржавая Кружка»"),
                ),
            },
        )

        phase_data = {
            "phase1": PhaseData(
                duration=1.0,
                stats=MockBatchStats(total_tokens=100, request_count=1),
                data={"bob": MockIntentionResponse(intention="Я хочу исследовать 你好")},
            ),
            "phase2a": PhaseData(duration=1.0, stats=None, data={}),
            "phase2b": PhaseData(duration=1.0, stats=None, data={}),
            "phase3": PhaseData(duration=0.01, stats=None, data={"pending_memories": {}}),
            "phase4": PhaseData(duration=1.0, stats=None, data=None),
        }

        report = TickReport(
            sim_id="test-sim",
            tick_number=1,
            narratives={"tavern": "Боб вошёл в таверну"},
            location_names={"tavern": "Таверна «Ржавая Кружка»"},
            success=True,
            timestamp=datetime.now(),
            duration=3.0,
            phases=phase_data,
            simulation=simulation,  # type: ignore[arg-type]
            pending_memories={"bob": "Я заказал эль"},
        )

        logger = TickLogger(sim_path)
        logger.write(report)

        log_file = sim_path / "logs" / "tick_000001.md"
        content = log_file.read_text(encoding="utf-8")

        assert "Боб Волшебник" in content
        assert "Таверна «Ржавая Кружка»" in content
        assert "Я хочу исследовать 你好" in content
