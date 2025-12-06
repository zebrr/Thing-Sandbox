"""Tests for phase stubs."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Config
from src.phases import (
    CharacterUpdate,
    LocationUpdate,
    MasterOutput,
    execute_phase1,
    execute_phase3,
    execute_phase4,
)
from src.phases.phase1 import IntentionResponse
from src.utils.storage import (
    Character,
    CharacterIdentity,
    CharacterMemory,
    CharacterState,
    Location,
    LocationIdentity,
    LocationState,
    Simulation,
    load_simulation,
)


@pytest.fixture
def demo_sim() -> Simulation:
    """Load demo simulation."""
    return load_simulation(Path("simulations/demo-sim"))


@pytest.fixture
def config() -> Config:
    """Load config."""
    return Config.load()


@pytest.fixture
def empty_sim() -> Simulation:
    """Create empty simulation for edge case testing."""
    return Simulation(
        id="empty-test",
        current_tick=0,
        created_at=datetime.now(),
        status="paused",
        characters={},
        locations={},
    )


@pytest.fixture
def sim_with_chars_in_locations() -> Simulation:
    """Create simulation with characters spread across locations."""
    return Simulation(
        id="test-sim",
        current_tick=5,
        created_at=datetime.now(),
        status="paused",
        characters={
            "alice": Character(
                identity=CharacterIdentity(
                    id="alice",
                    name="Alice",
                    description="A curious adventurer",
                ),
                state=CharacterState(
                    location="tavern",
                    internal_state="feeling curious",
                    external_intent="explore the room",
                ),
                memory=CharacterMemory(),
            ),
            "bob": Character(
                identity=CharacterIdentity(
                    id="bob",
                    name="Bob",
                    description="A grumpy dwarf",
                ),
                state=CharacterState(
                    location="forest",
                    internal_state=None,
                    external_intent=None,
                ),
                memory=CharacterMemory(),
            ),
        },
        locations={
            "tavern": Location(
                identity=LocationIdentity(
                    id="tavern",
                    name="The Rusty Tankard",
                    description="A cozy tavern",
                ),
                state=LocationState(moment="Evening, fire crackling"),
            ),
            "forest": Location(
                identity=LocationIdentity(
                    id="forest",
                    name="Dark Forest",
                    description="An ominous forest",
                ),
                state=LocationState(moment="Night, owls hooting"),
            ),
        },
    )


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Create mock LLM client for Phase 1 tests."""
    client = MagicMock()
    client.create_batch = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_phase1_returns_intentions_for_all_characters(
    demo_sim: Simulation, config: Config, mock_llm_client: MagicMock
) -> None:
    """Phase 1 returns intention for each character."""
    # Mock LLM to return intentions for all characters
    intentions = [
        IntentionResponse(intention=f"intention for {char_id}") for char_id in demo_sim.characters
    ]
    mock_llm_client.create_batch.return_value = intentions

    with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
        mock_renderer = MagicMock()
        mock_renderer.render.return_value = "rendered prompt"
        mock_renderer_class.return_value = mock_renderer

        result = await execute_phase1(demo_sim, config, mock_llm_client)

    assert result.success is True
    assert result.error is None
    assert isinstance(result.data, dict)

    # Should have intention for each character
    for char_id in demo_sim.characters:
        assert char_id in result.data
        assert isinstance(result.data[char_id], IntentionResponse)


@pytest.mark.asyncio
async def test_phase3_applies_results(demo_sim: Simulation, config: Config) -> None:
    """Phase 3 applies master_results and returns pending_memories."""
    # Create mock master_results instead of calling phase2a
    master_results: dict[str, MasterOutput] = {}
    for loc_id in demo_sim.locations:
        char_updates: list[CharacterUpdate] = []
        for char_id, char in demo_sim.characters.items():
            if char.state.location == loc_id:
                char_updates.append(
                    CharacterUpdate(
                        character_id=char_id,
                        location=loc_id,
                        internal_state=char.state.internal_state or "",
                        external_intent=char.state.external_intent or "",
                        memory_entry=f"Test memory for {char_id}",
                    )
                )
        master_results[loc_id] = MasterOutput(
            tick=demo_sim.current_tick,
            location_id=loc_id,
            characters=char_updates,
            location=LocationUpdate(),
        )

    result = await execute_phase3(demo_sim, config, master_results)

    assert result.success is True
    assert result.data is not None
    assert "pending_memories" in result.data
    assert result.error is None


@pytest.mark.asyncio
async def test_phase4_succeeds_with_no_op(demo_sim: Simulation, config: Config) -> None:
    """Phase 4 stub succeeds and returns None data."""
    pending_memories = {"char1": "memory1", "char2": "memory2"}
    result = await execute_phase4(demo_sim, config, None, pending_memories)  # type: ignore[arg-type]

    assert result.success is True
    assert result.data is None
    assert result.error is None


@pytest.mark.asyncio
async def test_phase1_handles_empty_simulation(
    empty_sim: Simulation, config: Config, mock_llm_client: MagicMock
) -> None:
    """Phase 1 handles simulation with no characters."""
    mock_llm_client.create_batch.return_value = []

    with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
        mock_renderer = MagicMock()
        mock_renderer.render.return_value = "rendered prompt"
        mock_renderer_class.return_value = mock_renderer

        result = await execute_phase1(empty_sim, config, mock_llm_client)

    assert result.success is True
    assert result.data == {}
