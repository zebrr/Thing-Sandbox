"""Integration tests for Phase 2a and 2b with real OpenAI API.

These tests require OPENAI_API_KEY environment variable.
They make real API calls and may incur costs.

Run with: pytest tests/integration/test_phase2_integration.py -v -s
"""

from datetime import datetime

import pytest

from src.config import Config
from src.phases.phase1 import execute as execute_phase1
from src.phases.phase2a import MasterOutput
from src.phases.phase2a import execute as execute_phase2a
from src.phases.phase2b import NarrativeResponse
from src.phases.phase2b import execute as execute_phase2b
from src.utils.llm import LLMClient
from src.utils.llm_adapters import OpenAIAdapter
from src.utils.storage import (
    Character,
    CharacterIdentity,
    CharacterMemory,
    CharacterState,
    Location,
    LocationConnection,
    LocationIdentity,
    LocationState,
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


@pytest.fixture
def test_simulation(config: Config) -> Simulation:
    """Create test simulation with two characters in one location."""
    return Simulation(
        id="test-phase2-sim",
        current_tick=0,
        created_at=datetime.now(),
        status="paused",
        characters={
            "alice": Character(
                identity=CharacterIdentity(
                    id="alice",
                    name="Alice",
                    description="A curious explorer who loves adventure.",
                    triggers="Gets excited when discovering new things.",
                ),
                state=CharacterState(
                    location="tavern",
                    internal_state="Eager to explore",
                    external_intent="Looking for companions",
                ),
                memory=CharacterMemory(),
            ),
            "bob": Character(
                identity=CharacterIdentity(
                    id="bob",
                    name="Bob",
                    description="A cautious merchant who values safety.",
                    triggers="Becomes nervous in dangerous situations.",
                ),
                state=CharacterState(
                    location="tavern",
                    internal_state="Relaxed",
                    external_intent="Selling wares",
                ),
                memory=CharacterMemory(),
            ),
        },
        locations={
            "tavern": Location(
                identity=LocationIdentity(
                    id="tavern",
                    name="The Rusty Tankard",
                    description="A cozy tavern with a warm fireplace and wooden tables.",
                    connections=[
                        LocationConnection(
                            location_id="market",
                            description="Through the door to the market square",
                        ),
                    ],
                ),
                state=LocationState(moment="Evening, the tavern is moderately busy"),
            ),
            "market": Location(
                identity=LocationIdentity(
                    id="market",
                    name="Market Square",
                    description="A bustling market with various stalls and vendors.",
                    connections=[
                        LocationConnection(location_id="tavern", description="Path to the tavern"),
                    ],
                ),
                state=LocationState(moment="Quiet, most vendors have closed for the day"),
            ),
        },
    )


def make_char_entities(simulation: Simulation) -> list[dict]:
    """Create character entity dicts for LLMClient."""
    return [char.model_dump() for char in simulation.characters.values()]


def make_loc_entities(simulation: Simulation) -> list[dict]:
    """Create location entity dicts for LLMClient."""
    return [loc.model_dump() for loc in simulation.locations.values()]


class TestPhase2aIntegration:
    """Integration tests for Phase 2a with real LLM."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_phase2a_real_llm(self, config: Config, test_simulation: Simulation) -> None:
        """Phase 2a generates valid MasterOutput for all locations."""
        # First run Phase 1 to get intentions
        char_entities = make_char_entities(test_simulation)
        adapter1 = OpenAIAdapter(config.phase1)
        client1 = LLMClient(
            adapter=adapter1,
            entities=char_entities,
            default_depth=config.phase1.response_chain_depth,
        )

        result1 = await execute_phase1(test_simulation, config, client1)
        assert result1.success is True

        intentions = {char_id: resp.intention for char_id, resp in result1.data.items()}

        # Now run Phase 2a
        loc_entities = make_loc_entities(test_simulation)
        adapter2a = OpenAIAdapter(config.phase2a)
        client2a = LLMClient(
            adapter=adapter2a,
            entities=loc_entities,
            default_depth=config.phase2a.response_chain_depth,
        )

        result2a = await execute_phase2a(test_simulation, config, client2a, intentions)

        assert result2a.success is True
        assert "tavern" in result2a.data
        assert "market" in result2a.data

        # Check tavern has both characters
        tavern_result = result2a.data["tavern"]
        assert isinstance(tavern_result, MasterOutput)
        assert "alice" in tavern_result.characters_dict
        assert "bob" in tavern_result.characters_dict

        # Check character updates are valid
        for char_id, update in tavern_result.characters_dict.items():
            assert update.memory_entry  # Non-empty
            assert update.location  # Has location

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_phase2a_character_updates_valid(
        self, config: Config, test_simulation: Simulation
    ) -> None:
        """Phase 2a produces valid character updates with non-empty memory entries."""
        char_entities = make_char_entities(test_simulation)
        adapter1 = OpenAIAdapter(config.phase1)
        client1 = LLMClient(adapter=adapter1, entities=char_entities, default_depth=0)

        result1 = await execute_phase1(test_simulation, config, client1)
        intentions = {char_id: resp.intention for char_id, resp in result1.data.items()}

        loc_entities = make_loc_entities(test_simulation)
        adapter2a = OpenAIAdapter(config.phase2a)
        client2a = LLMClient(adapter=adapter2a, entities=loc_entities, default_depth=0)

        result2a = await execute_phase2a(test_simulation, config, client2a, intentions)

        for loc_id, master in result2a.data.items():
            for char_id, update in master.characters_dict.items():
                # Memory entry should be non-empty (validated by Pydantic min_length=1)
                assert len(update.memory_entry) >= 1
                # Location should be a known location
                assert update.location in test_simulation.locations


class TestPhase2bIntegration:
    """Integration tests for Phase 2b with real LLM."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_phase2b_real_llm(self, config: Config, test_simulation: Simulation) -> None:
        """Phase 2b generates readable narratives."""
        # Phase 1
        char_entities = make_char_entities(test_simulation)
        adapter1 = OpenAIAdapter(config.phase1)
        client1 = LLMClient(adapter=adapter1, entities=char_entities, default_depth=0)
        result1 = await execute_phase1(test_simulation, config, client1)
        intentions = {char_id: resp.intention for char_id, resp in result1.data.items()}

        # Phase 2a
        loc_entities = make_loc_entities(test_simulation)
        adapter2a = OpenAIAdapter(config.phase2a)
        client2a = LLMClient(adapter=adapter2a, entities=loc_entities, default_depth=0)
        result2a = await execute_phase2a(test_simulation, config, client2a, intentions)

        # Phase 2b
        loc_entities_2b = make_loc_entities(test_simulation)
        adapter2b = OpenAIAdapter(config.phase2b)
        client2b = LLMClient(adapter=adapter2b, entities=loc_entities_2b, default_depth=0)

        result2b = await execute_phase2b(
            test_simulation, config, client2b, result2a.data, intentions
        )

        assert result2b.success is True
        assert "tavern" in result2b.data
        assert "market" in result2b.data

        # Check narratives are valid
        for loc_id, narrative_resp in result2b.data.items():
            assert isinstance(narrative_resp, NarrativeResponse)
            assert len(narrative_resp.narrative) > 0

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_phase2b_narrative_not_empty(
        self, config: Config, test_simulation: Simulation
    ) -> None:
        """Phase 2b produces non-empty narratives for all locations."""
        # Phase 1
        char_entities = make_char_entities(test_simulation)
        adapter1 = OpenAIAdapter(config.phase1)
        client1 = LLMClient(adapter=adapter1, entities=char_entities, default_depth=0)
        result1 = await execute_phase1(test_simulation, config, client1)
        intentions = {char_id: resp.intention for char_id, resp in result1.data.items()}

        # Phase 2a
        loc_entities = make_loc_entities(test_simulation)
        adapter2a = OpenAIAdapter(config.phase2a)
        client2a = LLMClient(adapter=adapter2a, entities=loc_entities, default_depth=0)
        result2a = await execute_phase2a(test_simulation, config, client2a, intentions)

        # Phase 2b
        loc_entities_2b = make_loc_entities(test_simulation)
        adapter2b = OpenAIAdapter(config.phase2b)
        client2b = LLMClient(adapter=adapter2b, entities=loc_entities_2b, default_depth=0)

        result2b = await execute_phase2b(
            test_simulation, config, client2b, result2a.data, intentions
        )

        for loc_id, narrative_resp in result2b.data.items():
            # Narrative should have actual content (not just whitespace)
            assert narrative_resp.narrative.strip()


class TestPhase2FullChain:
    """Integration tests for Phase 1 → 2a → 2b chain."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(300)
    async def test_phase2_full_chain(self, config: Config, test_simulation: Simulation) -> None:
        """Full chain Phase 1 → 2a → 2b works together."""
        # Phase 1: Generate intentions
        char_entities = make_char_entities(test_simulation)
        adapter1 = OpenAIAdapter(config.phase1)
        client1 = LLMClient(adapter=adapter1, entities=char_entities, default_depth=0)

        result1 = await execute_phase1(test_simulation, config, client1)

        assert result1.success is True
        assert "alice" in result1.data
        assert "bob" in result1.data

        # Extract intentions
        intentions = {char_id: resp.intention for char_id, resp in result1.data.items()}

        # Phase 2a: Scene resolution
        loc_entities = make_loc_entities(test_simulation)
        adapter2a = OpenAIAdapter(config.phase2a)
        client2a = LLMClient(adapter=adapter2a, entities=loc_entities, default_depth=0)

        result2a = await execute_phase2a(test_simulation, config, client2a, intentions)

        assert result2a.success is True
        # Tavern should have both characters resolved
        assert "alice" in result2a.data["tavern"].characters_dict
        assert "bob" in result2a.data["tavern"].characters_dict

        # Phase 2b: Narrative generation
        loc_entities_2b = make_loc_entities(test_simulation)
        adapter2b = OpenAIAdapter(config.phase2b)
        client2b = LLMClient(adapter=adapter2b, entities=loc_entities_2b, default_depth=0)

        result2b = await execute_phase2b(
            test_simulation, config, client2b, result2a.data, intentions
        )

        assert result2b.success is True
        # Should have narratives for all locations
        assert len(result2b.data) == len(test_simulation.locations)

        # Narratives should be substantial (more than just a few words)
        for loc_id, narrative_resp in result2b.data.items():
            assert len(narrative_resp.narrative) >= 10

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_usage_tracked_in_entities(
        self, config: Config, test_simulation: Simulation
    ) -> None:
        """Usage is tracked in location entities after Phase 2a/2b."""
        # Phase 1
        char_entities = make_char_entities(test_simulation)
        adapter1 = OpenAIAdapter(config.phase1)
        client1 = LLMClient(adapter=adapter1, entities=char_entities, default_depth=0)
        result1 = await execute_phase1(test_simulation, config, client1)
        intentions = {char_id: resp.intention for char_id, resp in result1.data.items()}

        # Phase 2a with tracked entities
        loc_entities = make_loc_entities(test_simulation)
        adapter2a = OpenAIAdapter(config.phase2a)
        client2a = LLMClient(adapter=adapter2a, entities=loc_entities, default_depth=0)

        await execute_phase2a(test_simulation, config, client2a, intentions)

        # Check usage tracked
        stats = client2a.get_last_batch_stats()
        assert stats.total_tokens > 0
        assert stats.request_count == len(test_simulation.locations)
