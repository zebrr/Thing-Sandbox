"""Integration tests for Phase 4 with real OpenAI API.

These tests require OPENAI_API_KEY environment variable.
They make real API calls and may incur costs.

Run with: pytest tests/integration/test_phase4_integration.py -v -s -m integration
"""

from datetime import datetime

import pytest

from src.config import Config
from src.phases.phase4 import execute
from src.utils.llm import LLMClient
from src.utils.llm_adapters import OpenAIAdapter
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

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]


@pytest.fixture
def config() -> Config:
    """Load config, skip if no API key."""
    cfg = Config.load()
    if not cfg.openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env")
    return cfg


def make_character_with_full_memory(
    char_id: str,
    name: str,
    location: str,
    max_cells: int,
    description: str = "A test character",
) -> Character:
    """Create character with full memory queue (triggers summarization).

    Args:
        char_id: Character identifier.
        name: Character display name.
        location: Current location ID.
        max_cells: K value - number of cells to create.
        description: Character description.

    Returns:
        Character with exactly max_cells memory cells.
    """
    # Create cells in order: newest first [K-1, K-2, ..., 0]
    cells = [
        MemoryCell(
            tick=max_cells - 1 - i,
            text=f"Память тика {max_cells - 1 - i}: события и наблюдения",
        )
        for i in range(max_cells)
    ]

    return Character(
        identity=CharacterIdentity(
            id=char_id,
            name=name,
            description=description,
        ),
        state=CharacterState(location=location),
        memory=CharacterMemory(
            cells=cells,
            summary="Начальная сводка: персонаж начал свой путь",
        ),
    )


def make_character_with_space(
    char_id: str,
    name: str,
    location: str,
    current_cells: int,
) -> Character:
    """Create character with space in memory queue (no summarization needed)."""
    cells = [
        MemoryCell(tick=i, text=f"Memory from tick {i}") for i in range(current_cells - 1, -1, -1)
    ]

    return Character(
        identity=CharacterIdentity(
            id=char_id,
            name=name,
            description="A test character with memory space",
        ),
        state=CharacterState(location=location),
        memory=CharacterMemory(cells=cells, summary=""),
    )


def make_location(loc_id: str, name: str) -> Location:
    """Create a test location."""
    return Location(
        identity=LocationIdentity(
            id=loc_id,
            name=name,
            description="A test location",
            connections=[],
        ),
        state=LocationState(moment=""),
    )


def make_test_simulation(
    characters: dict[str, Character],
    locations: dict[str, Location],
    current_tick: int,
) -> Simulation:
    """Create test simulation with given characters and locations."""
    return Simulation(
        id="test-phase4-sim",
        current_tick=current_tick,
        created_at=datetime.now(),
        status="running",
        characters=characters,
        locations=locations,
    )


class TestPhase4RealLLM:
    """Integration tests with real LLM calls."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_summarize_memory_real_llm(self, config: Config) -> None:
        """Memory is summarized correctly by real LLM.

        Verifies:
        - Phase 4 successfully calls LLM for summarization
        - Summary is updated with new content
        - Oldest cell is removed, new cell is added at front
        - Cell count remains at K
        """
        max_cells = config.simulation.memory_cells  # K=5

        # Create character with full memory
        alice = make_character_with_full_memory(
            "alice",
            "Алиса",
            "tavern",
            max_cells,
            description="Молодая исследовательница, любопытная и смелая",
        )
        original_summary = alice.memory.summary
        original_oldest_cell = alice.memory.cells[-1].text

        tavern = make_location("tavern", "Таверна")
        sim = make_test_simulation(
            {"alice": alice},
            {"tavern": tavern},
            current_tick=max_cells,  # Next tick after filling memory
        )

        pending_memory = "Я встретила загадочного незнакомца в плаще"
        pending = {"alice": pending_memory}

        # Create real LLM client
        entities = [alice.model_dump()]
        adapter = OpenAIAdapter(config.phase4)
        llm_client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=config.phase4.response_chain_depth,
        )

        # Execute Phase 4
        result = await execute(sim, config, llm_client, pending)

        # Verify result
        assert result.success is True
        assert result.data is None

        # Summary was updated (different from original)
        assert alice.memory.summary != original_summary
        assert len(alice.memory.summary) > 0

        # Cell count is still K
        assert len(alice.memory.cells) == max_cells

        # New cell is at front with pending memory
        assert alice.memory.cells[0].text == pending_memory
        assert alice.memory.cells[0].tick == max_cells

        # Oldest cell was removed (its text no longer in cells)
        cell_texts = [c.text for c in alice.memory.cells]
        assert original_oldest_cell not in cell_texts

        # Cleanup - delete response chains
        for entity in entities:
            if "_openai" in entity:
                for chain_key in list(entity["_openai"].keys()):
                    if chain_key.endswith("_chain"):
                        for resp_id in entity["_openai"][chain_key]:
                            try:
                                await adapter.delete_response(resp_id)
                            except Exception:
                                pass

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_no_llm_call_when_space_available(self, config: Config) -> None:
        """No LLM call when memory has space.

        Verifies:
        - Character with less than K cells doesn't trigger LLM
        - Memory is added directly
        - Usage stats show no requests for this character
        """
        current_cells = 2  # Less than K (max_cells=5 from config)

        alice = make_character_with_space("alice", "Alice", "tavern", current_cells)
        tavern = make_location("tavern", "Tavern")
        sim = make_test_simulation(
            {"alice": alice},
            {"tavern": tavern},
            current_tick=current_cells,
        )

        pending_memory = "New memory entry"
        pending = {"alice": pending_memory}

        # Create LLM client (won't be used but needed for interface)
        entities = [alice.model_dump()]
        adapter = OpenAIAdapter(config.phase4)
        llm_client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=config.phase4.response_chain_depth,
        )

        # Execute Phase 4
        result = await execute(sim, config, llm_client, pending)

        # Verify result
        assert result.success is True

        # Cell was added (count increased)
        assert len(alice.memory.cells) == current_cells + 1

        # New cell is at front
        assert alice.memory.cells[0].text == pending_memory

        # No LLM requests were made - check batch stats
        stats = llm_client.get_last_batch_stats()
        assert stats.request_count == 0

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_usage_tracked_after_summarization(self, config: Config) -> None:
        """Usage statistics are tracked after summarization.

        Verifies:
        - After LLM call, usage stats show tokens were used
        - Request count is correct
        """
        max_cells = config.simulation.memory_cells

        alice = make_character_with_full_memory(
            "alice", "Alice", "tavern", max_cells, description="Test character for usage tracking"
        )
        tavern = make_location("tavern", "Tavern")
        sim = make_test_simulation(
            {"alice": alice},
            {"tavern": tavern},
            current_tick=max_cells,
        )

        pending = {"alice": "New memory for usage test"}

        entities = [alice.model_dump()]
        adapter = OpenAIAdapter(config.phase4)
        llm_client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=config.phase4.response_chain_depth,
        )

        # Execute Phase 4
        await execute(sim, config, llm_client, pending)

        # Check usage stats
        stats = llm_client.get_last_batch_stats()
        assert stats.request_count == 1
        assert stats.total_tokens > 0

        # Cleanup
        for entity in entities:
            if "_openai" in entity:
                for chain_key in list(entity["_openai"].keys()):
                    if chain_key.endswith("_chain"):
                        for resp_id in entity["_openai"][chain_key]:
                            try:
                                await adapter.delete_response(resp_id)
                            except Exception:
                                pass
