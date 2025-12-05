"""Tests for Phase 3: Apply arbitration results."""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.config import Config
from src.phases.phase2a import CharacterUpdate, LocationUpdate, MasterOutput
from src.phases.phase3 import execute
from src.utils.storage import (
    Character,
    CharacterIdentity,
    CharacterMemory,
    CharacterState,
    Location,
    LocationIdentity,
    LocationState,
    Simulation,
)


@pytest.fixture
def config() -> Config:
    """Load config."""
    return Config.load()


@pytest.fixture
def simple_sim() -> Simulation:
    """Create simple simulation with one character and one location."""
    return Simulation(
        id="test-sim",
        current_tick=5,
        created_at=datetime.now(),
        status="paused",
        characters={
            "bob": Character(
                identity=CharacterIdentity(
                    id="bob",
                    name="Bob",
                    description="A brave knight",
                ),
                state=CharacterState(
                    location="tavern",
                    internal_state="calm",
                    external_intent="rest",
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
        },
    )


@pytest.fixture
def multi_sim() -> Simulation:
    """Create simulation with multiple characters and locations."""
    return Simulation(
        id="multi-test",
        current_tick=10,
        created_at=datetime.now(),
        status="paused",
        characters={
            "alice": Character(
                identity=CharacterIdentity(
                    id="alice",
                    name="Алиса",  # Cyrillic test
                    description="A curious adventurer",
                ),
                state=CharacterState(
                    location="tavern",
                    internal_state="curious",
                    external_intent="explore",
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
                    internal_state="tired",
                    external_intent="find shelter",
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
                state=LocationState(moment="Evening"),
            ),
            "forest": Location(
                identity=LocationIdentity(
                    id="forest",
                    name="Dark Forest",
                    description="An ominous forest",
                ),
                state=LocationState(moment="Night"),
            ),
        },
    )


# =============================================================================
# Character Updates
# =============================================================================


@pytest.mark.asyncio
async def test_update_character_location(simple_sim: Simulation, config: Config) -> None:
    """Character location changes correctly."""
    # Add a second location for movement
    simple_sim.locations["forest"] = Location(
        identity=LocationIdentity(id="forest", name="Forest", description="Trees"),
        state=LocationState(moment="Day"),
    )

    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="forest",  # Move to forest
                    internal_state="excited",
                    external_intent="explore",
                    memory_entry="I left the tavern",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert simple_sim.characters["bob"].state.location == "forest"


@pytest.mark.asyncio
async def test_update_character_internal_state(simple_sim: Simulation, config: Config) -> None:
    """Character internal_state is updated."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="очень взволнован",  # Cyrillic
                    external_intent="rest",
                    memory_entry="Something happened",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert simple_sim.characters["bob"].state.internal_state == "очень взволнован"


@pytest.mark.asyncio
async def test_update_character_external_intent(simple_sim: Simulation, config: Config) -> None:
    """Character external_intent is updated."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="calm",
                    external_intent="fight the dragon",
                    memory_entry="I decided to fight",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert simple_sim.characters["bob"].state.external_intent == "fight the dragon"


@pytest.mark.asyncio
async def test_update_multiple_characters(multi_sim: Simulation, config: Config) -> None:
    """Batch update works for multiple characters."""
    master_results = {
        "tavern": MasterOutput(
            tick=10,
            location_id="tavern",
            characters={
                "alice": CharacterUpdate(
                    location="tavern",
                    internal_state="happy",
                    external_intent="drink",
                    memory_entry="I ordered ale",
                ),
            },
            location=LocationUpdate(),
        ),
        "forest": MasterOutput(
            tick=10,
            location_id="forest",
            characters={
                "bob": CharacterUpdate(
                    location="forest",
                    internal_state="scared",
                    external_intent="run",
                    memory_entry="I saw a wolf",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    await execute(multi_sim, config, master_results)

    assert multi_sim.characters["alice"].state.internal_state == "happy"
    assert multi_sim.characters["bob"].state.internal_state == "scared"


# =============================================================================
# Location Updates
# =============================================================================


@pytest.mark.asyncio
async def test_update_location_moment(simple_sim: Simulation, config: Config) -> None:
    """Location moment changes when not None."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="calm",
                    external_intent="rest",
                    memory_entry="Time passed",
                ),
            },
            location=LocationUpdate(moment="Midnight, silence"),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert simple_sim.locations["tavern"].state.moment == "Midnight, silence"


@pytest.mark.asyncio
async def test_update_location_moment_null(simple_sim: Simulation, config: Config) -> None:
    """Location moment unchanged when None."""
    original_moment = simple_sim.locations["tavern"].state.moment

    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="calm",
                    external_intent="rest",
                    memory_entry="Nothing changed",
                ),
            },
            location=LocationUpdate(moment=None),  # Explicit None
        ),
    }

    await execute(simple_sim, config, master_results)

    assert simple_sim.locations["tavern"].state.moment == original_moment


@pytest.mark.asyncio
async def test_update_location_description(simple_sim: Simulation, config: Config) -> None:
    """Location description changes when not None."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="calm",
                    external_intent="rest",
                    memory_entry="The place changed",
                ),
            },
            location=LocationUpdate(description="A burned-down tavern"),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert simple_sim.locations["tavern"].identity.description == "A burned-down tavern"


@pytest.mark.asyncio
async def test_update_location_description_null(simple_sim: Simulation, config: Config) -> None:
    """Location description unchanged when None."""
    original_desc = simple_sim.locations["tavern"].identity.description

    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="calm",
                    external_intent="rest",
                    memory_entry="Normal day",
                ),
            },
            location=LocationUpdate(description=None),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert simple_sim.locations["tavern"].identity.description == original_desc


# =============================================================================
# Memory Collection
# =============================================================================


@pytest.mark.asyncio
async def test_collect_memory_entries(multi_sim: Simulation, config: Config) -> None:
    """All memory entries collected in pending_memories."""
    master_results = {
        "tavern": MasterOutput(
            tick=10,
            location_id="tavern",
            characters={
                "alice": CharacterUpdate(
                    location="tavern",
                    internal_state="happy",
                    external_intent="drink",
                    memory_entry="Я заказала эль",  # Cyrillic
                ),
            },
            location=LocationUpdate(),
        ),
        "forest": MasterOutput(
            tick=10,
            location_id="forest",
            characters={
                "bob": CharacterUpdate(
                    location="forest",
                    internal_state="scared",
                    external_intent="run",
                    memory_entry="I saw a wolf",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    result = await execute(multi_sim, config, master_results)

    assert "alice" in result.data["pending_memories"]
    assert "bob" in result.data["pending_memories"]
    assert result.data["pending_memories"]["alice"] == "Я заказала эль"
    assert result.data["pending_memories"]["bob"] == "I saw a wolf"


@pytest.mark.asyncio
async def test_memory_entries_match_characters(simple_sim: Simulation, config: Config) -> None:
    """Memory entries correctly mapped to character IDs."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="calm",
                    external_intent="rest",
                    memory_entry="Specific memory for Bob",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    result = await execute(simple_sim, config, master_results)

    assert len(result.data["pending_memories"]) == 1
    assert result.data["pending_memories"]["bob"] == "Specific memory for Bob"


# =============================================================================
# Validation & Fallbacks
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_location_id_skipped(simple_sim: Simulation, config: Config) -> None:
    """Unknown location in master_results is skipped."""
    master_results = {
        "mars": MasterOutput(  # Unknown location
            tick=5,
            location_id="mars",
            characters={},
            location=LocationUpdate(),
        ),
    }

    result = await execute(simple_sim, config, master_results)

    assert result.success is True
    assert result.data["pending_memories"] == {}


@pytest.mark.asyncio
async def test_invalid_char_id_skipped(simple_sim: Simulation, config: Config) -> None:
    """Unknown character in master_results is skipped."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "ghost": CharacterUpdate(  # Unknown character
                    location="tavern",
                    internal_state="spooky",
                    external_intent="haunt",
                    memory_entry="Boo!",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    result = await execute(simple_sim, config, master_results)

    assert result.success is True
    assert "ghost" not in result.data["pending_memories"]


@pytest.mark.asyncio
async def test_invalid_target_location_keeps_current(
    simple_sim: Simulation, config: Config
) -> None:
    """Character stays in current location if target is invalid."""
    original_location = simple_sim.characters["bob"].state.location

    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="nowhere",  # Invalid target
                    internal_state="confused",
                    external_intent="find way",
                    memory_entry="I tried to go somewhere",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    await execute(simple_sim, config, master_results)

    # Location unchanged, but other fields updated
    assert simple_sim.characters["bob"].state.location == original_location
    assert simple_sim.characters["bob"].state.internal_state == "confused"


@pytest.mark.asyncio
async def test_fallback_logs_warning(simple_sim: Simulation, config: Config) -> None:
    """Logger.warning is called for validation failures."""
    master_results = {
        "unknown_location": MasterOutput(
            tick=5,
            location_id="unknown_location",
            characters={},
            location=LocationUpdate(),
        ),
    }

    with patch("src.phases.phase3.logger") as mock_logger:
        await execute(simple_sim, config, master_results)
        mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def test_fallback_prints_console(simple_sim: Simulation, config: Config, capsys) -> None:
    """Print with warning emoji prefix for validation failures."""
    master_results = {
        "unknown_location": MasterOutput(
            tick=5,
            location_id="unknown_location",
            characters={},
            location=LocationUpdate(),
        ),
    }

    await execute(simple_sim, config, master_results)

    captured = capsys.readouterr()
    assert "⚠️" in captured.out
    assert "unknown_location" in captured.out


# =============================================================================
# Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_empty_master_results(simple_sim: Simulation, config: Config) -> None:
    """Empty dict returns empty pending_memories."""
    result = await execute(simple_sim, config, {})

    assert result.success is True
    assert result.data["pending_memories"] == {}


@pytest.mark.asyncio
async def test_empty_characters_in_location(simple_sim: Simulation, config: Config) -> None:
    """Location with no characters still processes location updates."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={},  # No character updates
            location=LocationUpdate(moment="New moment"),
        ),
    }

    result = await execute(simple_sim, config, master_results)

    assert simple_sim.locations["tavern"].state.moment == "New moment"
    assert result.data["pending_memories"] == {}


@pytest.mark.asyncio
async def test_single_location_single_character(simple_sim: Simulation, config: Config) -> None:
    """Minimal case: one location, one character."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="new_state",
                    external_intent="new_intent",
                    memory_entry="new_memory",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    result = await execute(simple_sim, config, master_results)

    assert result.success is True
    assert simple_sim.characters["bob"].state.internal_state == "new_state"
    assert result.data["pending_memories"]["bob"] == "new_memory"


@pytest.mark.asyncio
async def test_multiple_locations(multi_sim: Simulation, config: Config) -> None:
    """Multiple locations processed correctly."""
    master_results = {
        "tavern": MasterOutput(
            tick=10,
            location_id="tavern",
            characters={
                "alice": CharacterUpdate(
                    location="tavern",
                    internal_state="state_a",
                    external_intent="intent_a",
                    memory_entry="memory_a",
                ),
            },
            location=LocationUpdate(moment="Tavern moment"),
        ),
        "forest": MasterOutput(
            tick=10,
            location_id="forest",
            characters={
                "bob": CharacterUpdate(
                    location="forest",
                    internal_state="state_b",
                    external_intent="intent_b",
                    memory_entry="memory_b",
                ),
            },
            location=LocationUpdate(moment="Forest moment"),
        ),
    }

    result = await execute(multi_sim, config, master_results)

    assert multi_sim.locations["tavern"].state.moment == "Tavern moment"
    assert multi_sim.locations["forest"].state.moment == "Forest moment"
    assert len(result.data["pending_memories"]) == 2


# =============================================================================
# Result Structure
# =============================================================================


@pytest.mark.asyncio
async def test_result_success_always_true(simple_sim: Simulation, config: Config) -> None:
    """Success is True even with validation fallbacks."""
    master_results = {
        "invalid_location": MasterOutput(
            tick=5,
            location_id="invalid_location",
            characters={
                "ghost": CharacterUpdate(
                    location="nowhere",
                    internal_state="x",
                    external_intent="y",
                    memory_entry="z",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    result = await execute(simple_sim, config, master_results)

    assert result.success is True


@pytest.mark.asyncio
async def test_result_data_has_pending_memories(simple_sim: Simulation, config: Config) -> None:
    """Result data contains 'pending_memories' key."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="x",
                    external_intent="y",
                    memory_entry="z",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    result = await execute(simple_sim, config, master_results)

    assert "pending_memories" in result.data


@pytest.mark.asyncio
async def test_result_pending_memories_type(simple_sim: Simulation, config: Config) -> None:
    """pending_memories is dict[str, str]."""
    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="x",
                    external_intent="y",
                    memory_entry="test_memory",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    result = await execute(simple_sim, config, master_results)

    pending = result.data["pending_memories"]
    assert isinstance(pending, dict)
    for key, value in pending.items():
        assert isinstance(key, str)
        assert isinstance(value, str)


# =============================================================================
# Mutation
# =============================================================================


@pytest.mark.asyncio
async def test_simulation_mutated_in_place(simple_sim: Simulation, config: Config) -> None:
    """Original simulation object is changed."""
    original_state = simple_sim.characters["bob"].state.internal_state

    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="mutated_state",
                    external_intent="x",
                    memory_entry="y",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert simple_sim.characters["bob"].state.internal_state != original_state
    assert simple_sim.characters["bob"].state.internal_state == "mutated_state"


@pytest.mark.asyncio
async def test_no_new_characters_created(simple_sim: Simulation, config: Config) -> None:
    """Only existing characters updated, no new ones created."""
    original_char_count = len(simple_sim.characters)

    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="x",
                    external_intent="y",
                    memory_entry="z",
                ),
                "ghost": CharacterUpdate(  # Unknown - should be skipped
                    location="tavern",
                    internal_state="a",
                    external_intent="b",
                    memory_entry="c",
                ),
            },
            location=LocationUpdate(),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert len(simple_sim.characters) == original_char_count
    assert "ghost" not in simple_sim.characters


@pytest.mark.asyncio
async def test_no_new_locations_created(simple_sim: Simulation, config: Config) -> None:
    """Only existing locations updated, no new ones created."""
    original_loc_count = len(simple_sim.locations)

    master_results = {
        "tavern": MasterOutput(
            tick=5,
            location_id="tavern",
            characters={
                "bob": CharacterUpdate(
                    location="tavern",
                    internal_state="x",
                    external_intent="y",
                    memory_entry="z",
                ),
            },
            location=LocationUpdate(),
        ),
        "mars": MasterOutput(  # Unknown - should be skipped
            tick=5,
            location_id="mars",
            characters={},
            location=LocationUpdate(moment="Red dust"),
        ),
    }

    await execute(simple_sim, config, master_results)

    assert len(simple_sim.locations) == original_loc_count
    assert "mars" not in simple_sim.locations
