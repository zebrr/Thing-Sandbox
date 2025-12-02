"""Tests for phase stubs."""

from datetime import datetime
from pathlib import Path

import pytest

from src.config import Config
from src.phases import (
    execute_phase1,
    execute_phase2a,
    execute_phase2b,
    execute_phase3,
    execute_phase4,
)
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


@pytest.mark.asyncio
async def test_phase1_returns_intentions_for_all_characters(
    demo_sim: Simulation, config: Config
) -> None:
    """Phase 1 stub returns intention for each character."""
    result = await execute_phase1(demo_sim, config, None)  # type: ignore[arg-type]

    assert result.success is True
    assert result.error is None
    assert isinstance(result.data, dict)

    # Should have intention for each character
    for char_id in demo_sim.characters:
        assert char_id in result.data
        assert result.data[char_id]["intention"] == "idle"


@pytest.mark.asyncio
async def test_phase2a_returns_master_for_all_locations(
    demo_sim: Simulation, config: Config
) -> None:
    """Phase 2a stub returns Master output for each location."""
    result = await execute_phase2a(demo_sim, config, None)  # type: ignore[arg-type]

    assert result.success is True
    assert isinstance(result.data, dict)

    # Should have result for each location
    for loc_id in demo_sim.locations:
        assert loc_id in result.data
        assert result.data[loc_id]["location_id"] == loc_id
        assert "characters" in result.data[loc_id]
        assert "location" in result.data[loc_id]


@pytest.mark.asyncio
async def test_phase2b_returns_narratives_for_all_locations(
    demo_sim: Simulation, config: Config
) -> None:
    """Phase 2b stub returns narrative for each location."""
    result = await execute_phase2b(demo_sim, config, None)  # type: ignore[arg-type]

    assert result.success is True
    assert isinstance(result.data, dict)

    for loc_id in demo_sim.locations:
        assert loc_id in result.data
        assert "narrative" in result.data[loc_id]
        assert "[Stub]" in result.data[loc_id]["narrative"]


@pytest.mark.asyncio
async def test_phase3_succeeds_with_no_op(demo_sim: Simulation, config: Config) -> None:
    """Phase 3 stub succeeds and returns None data."""
    result = await execute_phase3(demo_sim, config, None)  # type: ignore[arg-type]

    assert result.success is True
    assert result.data is None
    assert result.error is None


@pytest.mark.asyncio
async def test_phase4_succeeds_with_no_op(demo_sim: Simulation, config: Config) -> None:
    """Phase 4 stub succeeds and returns None data."""
    result = await execute_phase4(demo_sim, config, None)  # type: ignore[arg-type]

    assert result.success is True
    assert result.data is None
    assert result.error is None


@pytest.mark.asyncio
async def test_phase1_handles_empty_simulation(empty_sim: Simulation, config: Config) -> None:
    """Phase 1 handles simulation with no characters."""
    result = await execute_phase1(empty_sim, config, None)  # type: ignore[arg-type]

    assert result.success is True
    assert result.data == {}


@pytest.mark.asyncio
async def test_phase2a_handles_empty_simulation(empty_sim: Simulation, config: Config) -> None:
    """Phase 2a handles simulation with no locations."""
    result = await execute_phase2a(empty_sim, config, None)  # type: ignore[arg-type]

    assert result.success is True
    assert result.data == {}


@pytest.mark.asyncio
async def test_phase2b_handles_empty_simulation(empty_sim: Simulation, config: Config) -> None:
    """Phase 2b handles simulation with no locations."""
    result = await execute_phase2b(empty_sim, config, None)  # type: ignore[arg-type]

    assert result.success is True
    assert result.data == {}


@pytest.mark.asyncio
async def test_phase2a_includes_characters_in_location(
    sim_with_chars_in_locations: Simulation, config: Config
) -> None:
    """Phase 2a includes character updates for characters in each location."""
    result = await execute_phase2a(sim_with_chars_in_locations, config, None)  # type: ignore[arg-type]

    assert result.success is True

    # Alice is in tavern
    tavern_result = result.data["tavern"]
    assert "alice" in tavern_result["characters"]
    assert "bob" not in tavern_result["characters"]
    assert tavern_result["characters"]["alice"]["location"] == "tavern"

    # Bob is in forest
    forest_result = result.data["forest"]
    assert "bob" in forest_result["characters"]
    assert "alice" not in forest_result["characters"]
    assert forest_result["characters"]["bob"]["location"] == "forest"


@pytest.mark.asyncio
async def test_phase2a_preserves_character_state(
    sim_with_chars_in_locations: Simulation, config: Config
) -> None:
    """Phase 2a preserves existing character internal/external state."""
    result = await execute_phase2a(sim_with_chars_in_locations, config, None)  # type: ignore[arg-type]

    alice_update = result.data["tavern"]["characters"]["alice"]
    assert alice_update["internal_state"] == "feeling curious"
    assert alice_update["external_intent"] == "explore the room"

    # Bob has None states, should become empty strings
    bob_update = result.data["forest"]["characters"]["bob"]
    assert bob_update["internal_state"] == ""
    assert bob_update["external_intent"] == ""


@pytest.mark.asyncio
async def test_phase2b_uses_location_name_in_narrative(
    sim_with_chars_in_locations: Simulation, config: Config
) -> None:
    """Phase 2b includes location name in narrative text."""
    result = await execute_phase2b(sim_with_chars_in_locations, config, None)  # type: ignore[arg-type]

    assert "The Rusty Tankard" in result.data["tavern"]["narrative"]
    assert "Dark Forest" in result.data["forest"]["narrative"]
