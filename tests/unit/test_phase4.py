"""Unit tests for Phase 4: Memory summarization."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.config import Config
from src.phases.phase4 import (
    SummaryResponse,
    _add_memory_cell,
    _partition_characters,
    execute,
)
from src.utils.llm_errors import LLMError, LLMRateLimitError
from src.utils.storage import (
    Character,
    CharacterIdentity,
    CharacterMemory,
    CharacterState,
    Location,
    LocationIdentity,
    LocationState,
    MemoryCell,
    Simulation,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config() -> Config:
    """Load config."""
    return Config.load()


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Create mock LLM client."""
    client = MagicMock()
    client.create_batch = AsyncMock()
    return client


def make_character(
    char_id: str,
    name: str,
    location: str,
    cells: list[MemoryCell] | None = None,
    summary: str = "",
) -> Character:
    """Create a test character with optional memory cells."""
    return Character(
        identity=CharacterIdentity(
            id=char_id,
            name=name,
            description=f"Test character {name}",
        ),
        state=CharacterState(location=location),
        memory=CharacterMemory(
            cells=cells or [],
            summary=summary,
        ),
    )


def make_memory_cells(count: int, start_tick: int = 0) -> list[MemoryCell]:
    """Create a list of memory cells.

    Cells are ordered newest first: [tick=count-1, tick=count-2, ..., tick=0]
    """
    return [
        MemoryCell(tick=start_tick + count - 1 - i, text=f"Memory from tick {start_tick + count - 1 - i}")
        for i in range(count)
    ]


def make_location(loc_id: str, name: str) -> Location:
    """Create a test location."""
    return Location(
        identity=LocationIdentity(
            id=loc_id,
            name=name,
            description=f"Test location {name}",
            connections=[],
        ),
        state=LocationState(moment=""),
    )


def make_simulation(
    characters: dict[str, Character],
    locations: dict[str, Location] | None = None,
    current_tick: int = 0,
    sim_id: str = "test-sim",
) -> Simulation:
    """Create a test simulation."""
    return Simulation(
        id=sim_id,
        current_tick=current_tick,
        created_at=datetime.now(),
        status="paused",
        characters=characters,
        locations=locations or {},
    )


def make_summary_response(summary: str = "Updated summary") -> SummaryResponse:
    """Create a test SummaryResponse."""
    return SummaryResponse(summary=summary)


# =============================================================================
# SummaryResponse Tests
# =============================================================================


class TestSummaryResponse:
    """Tests for SummaryResponse model."""

    def test_summary_response_creation(self) -> None:
        """SummaryResponse can be created with summary field."""
        response = SummaryResponse(summary="I remember the events clearly...")
        assert response.summary == "I remember the events clearly..."

    def test_summary_response_unicode(self) -> None:
        """SummaryResponse handles non-ASCII characters (Cyrillic)."""
        response = SummaryResponse(summary="Я помню встречу с незнакомцем у пруда")
        assert response.summary == "Я помню встречу с незнакомцем у пруда"

    def test_summary_response_empty_rejected(self) -> None:
        """SummaryResponse rejects empty string (min_length=1)."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            SummaryResponse(summary="")


# =============================================================================
# _partition_characters Tests
# =============================================================================


class TestPartitionCharacters:
    """Tests for _partition_characters helper."""

    def test_partition_mixed(self) -> None:
        """Mixed: some need summary, some have space."""
        # Alice has 5 cells (full), Bob has 2 cells (space)
        alice = make_character("alice", "Alice", "tavern", cells=make_memory_cells(5))
        bob = make_character("bob", "Bob", "tavern", cells=make_memory_cells(2))
        characters = {"alice": alice, "bob": bob}
        pending = {"alice": "new memory", "bob": "new memory"}

        needs, has_space = _partition_characters(characters, pending, max_cells=5)

        assert len(needs) == 1
        assert len(has_space) == 1
        assert needs[0].identity.id == "alice"
        assert has_space[0].identity.id == "bob"

    def test_partition_empty_cells(self) -> None:
        """New character with empty cells goes to has_space."""
        alice = make_character("alice", "Alice", "tavern", cells=[])
        characters = {"alice": alice}
        pending = {"alice": "new memory"}

        needs, has_space = _partition_characters(characters, pending, max_cells=5)

        assert len(needs) == 0
        assert len(has_space) == 1
        assert has_space[0].identity.id == "alice"


# =============================================================================
# execute() Tests - Batch Execution
# =============================================================================


class TestExecuteBatch:
    """Tests for batch execution in execute()."""

    @pytest.mark.asyncio
    async def test_execute_all_need_summary(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """All characters need summarization - batch is called."""
        alice = make_character(
            "alice", "Alice", "tavern",
            cells=make_memory_cells(5),
            summary="Old summary"
        )
        bob = make_character(
            "bob", "Bob", "forest",
            cells=make_memory_cells(5),
            summary="Old Bob summary"
        )
        tavern = make_location("tavern", "Tavern")
        forest = make_location("forest", "Forest")
        sim = make_simulation(
            {"alice": alice, "bob": bob},
            {"tavern": tavern, "forest": forest},
            current_tick=5,
        )
        pending = {"alice": "Alice's new memory", "bob": "Bob's new memory"}

        mock_llm_client.create_batch.return_value = [
            make_summary_response("Alice new summary"),
            make_summary_response("Bob new summary"),
        ]

        with patch("src.phases.phase4.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, pending)

        assert result.success is True
        assert result.data is None

        # Batch was called with 2 requests
        mock_llm_client.create_batch.assert_called_once()
        requests = mock_llm_client.create_batch.call_args[0][0]
        assert len(requests) == 2

        # Memories were updated
        assert alice.memory.summary == "Alice new summary"
        assert bob.memory.summary == "Bob new summary"
        assert len(alice.memory.cells) == 5
        assert len(bob.memory.cells) == 5
        assert alice.memory.cells[0].text == "Alice's new memory"
        assert bob.memory.cells[0].text == "Bob's new memory"

    @pytest.mark.asyncio
    async def test_execute_none_need_summary(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """No characters need summarization - no LLM call."""
        alice = make_character("alice", "Alice", "tavern", cells=make_memory_cells(2))
        bob = make_character("bob", "Bob", "tavern", cells=make_memory_cells(3))
        tavern = make_location("tavern", "Tavern")
        sim = make_simulation(
            {"alice": alice, "bob": bob},
            {"tavern": tavern},
            current_tick=5,
        )
        pending = {"alice": "Alice's memory", "bob": "Bob's memory"}

        with patch("src.phases.phase4.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, pending)

        assert result.success is True
        mock_llm_client.create_batch.assert_not_called()

        # Memories were added directly
        assert len(alice.memory.cells) == 3
        assert len(bob.memory.cells) == 4
        assert alice.memory.cells[0].text == "Alice's memory"
        assert bob.memory.cells[0].text == "Bob's memory"

    @pytest.mark.asyncio
    async def test_execute_mixed(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Mixed: one needs summary, one has space."""
        alice = make_character(
            "alice", "Alice", "tavern",
            cells=make_memory_cells(5),
            summary="Old summary"
        )
        bob = make_character("bob", "Bob", "tavern", cells=make_memory_cells(2))
        tavern = make_location("tavern", "Tavern")
        sim = make_simulation(
            {"alice": alice, "bob": bob},
            {"tavern": tavern},
            current_tick=5,
        )
        pending = {"alice": "Alice's memory", "bob": "Bob's memory"}

        mock_llm_client.create_batch.return_value = [
            make_summary_response("Alice new summary"),
        ]

        with patch("src.phases.phase4.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, pending)

        assert result.success is True

        # Only 1 LLM request (for Alice)
        requests = mock_llm_client.create_batch.call_args[0][0]
        assert len(requests) == 1
        assert requests[0].entity_key == "memory:alice"

        # Alice got summarization, Bob got direct add
        assert alice.memory.summary == "Alice new summary"
        assert len(alice.memory.cells) == 5
        assert len(bob.memory.cells) == 3
        assert alice.memory.cells[0].text == "Alice's memory"
        assert bob.memory.cells[0].text == "Bob's memory"


# =============================================================================
# execute() Tests - Fallback
# =============================================================================


class TestExecuteFallback:
    """Tests for fallback handling in execute()."""

    @pytest.mark.asyncio
    async def test_execute_llm_error_fallback(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """LLM error triggers fallback - memory unchanged."""
        original_cells = make_memory_cells(5)
        original_summary = "Original summary that should be preserved"
        alice = make_character(
            "alice", "Alice", "tavern",
            cells=original_cells.copy(),  # Copy to preserve original
            summary=original_summary,
        )
        tavern = make_location("tavern", "Tavern")
        sim = make_simulation(
            {"alice": alice},
            {"tavern": tavern},
            current_tick=5,
        )
        pending = {"alice": "New memory that should be discarded"}

        mock_llm_client.create_batch.return_value = [
            LLMRateLimitError("Rate limit exceeded"),
        ]

        with patch("src.phases.phase4.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, pending)

        # Phase still succeeds (graceful degradation)
        assert result.success is True

        # Memory is UNCHANGED
        assert alice.memory.summary == original_summary
        assert len(alice.memory.cells) == 5
        # New memory was NOT added
        assert alice.memory.cells[0].text != "New memory that should be discarded"

    @pytest.mark.asyncio
    async def test_fallback_preserves_existing_memory(
        self, config: Config, mock_llm_client: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Fallback preserves both cells and summary intact."""
        cells = [
            MemoryCell(tick=4, text="Memory tick 4"),
            MemoryCell(tick=3, text="Memory tick 3"),
            MemoryCell(tick=2, text="Memory tick 2"),
            MemoryCell(tick=1, text="Memory tick 1"),
            MemoryCell(tick=0, text="Memory tick 0"),
        ]
        alice = make_character(
            "alice", "Alice", "tavern",
            cells=cells,
            summary="Important preserved summary",
        )
        tavern = make_location("tavern", "Tavern")
        sim = make_simulation(
            {"alice": alice},
            {"tavern": tavern},
            current_tick=5,
        )
        pending = {"alice": "This will be lost"}

        mock_llm_client.create_batch.return_value = [
            LLMError("Generic error"),
        ]

        with patch("src.phases.phase4.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            import logging
            with caplog.at_level(logging.WARNING):
                await execute(sim, config, mock_llm_client, pending)

        # Check memory preserved exactly
        assert alice.memory.summary == "Important preserved summary"
        assert len(alice.memory.cells) == 5
        assert alice.memory.cells[0].text == "Memory tick 4"
        assert alice.memory.cells[-1].text == "Memory tick 0"

        # Warning was logged
        assert "alice" in caplog.text
        assert "fallback" in caplog.text


# =============================================================================
# execute() Tests - Edge Cases
# =============================================================================


class TestExecuteEdgeCases:
    """Tests for edge cases in execute()."""

    @pytest.mark.asyncio
    async def test_execute_empty_pending_memories(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Empty pending_memories - no updates, no errors."""
        alice = make_character("alice", "Alice", "tavern", cells=make_memory_cells(3))
        tavern = make_location("tavern", "Tavern")
        sim = make_simulation(
            {"alice": alice},
            {"tavern": tavern},
        )
        pending: dict[str, str] = {}

        with patch("src.phases.phase4.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, pending)

        assert result.success is True
        assert result.data is None
        mock_llm_client.create_batch.assert_not_called()
        # Memory unchanged
        assert len(alice.memory.cells) == 3


# =============================================================================
# _add_memory_cell Tests
# =============================================================================


class TestAddMemoryCell:
    """Tests for _add_memory_cell helper."""

    def test_add_cell_at_front(self) -> None:
        """New cell is inserted at index 0."""
        char = make_character("alice", "Alice", "tavern", cells=[])
        _add_memory_cell(char, 5, "New memory")

        assert len(char.memory.cells) == 1
        assert char.memory.cells[0].tick == 5
        assert char.memory.cells[0].text == "New memory"

    def test_add_cell_preserves_order(self) -> None:
        """Existing cells shift right when new cell added."""
        char = make_character(
            "alice", "Alice", "tavern",
            cells=[
                MemoryCell(tick=2, text="Second"),
                MemoryCell(tick=1, text="First"),
            ]
        )
        _add_memory_cell(char, 3, "Third")

        assert len(char.memory.cells) == 3
        assert char.memory.cells[0].text == "Third"
        assert char.memory.cells[1].text == "Second"
        assert char.memory.cells[2].text == "First"
