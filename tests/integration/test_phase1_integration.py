"""Integration tests for Phase 1 with real OpenAI API.

These tests require OPENAI_API_KEY environment variable.
They make real API calls and may incur costs.

Run with: pytest tests/integration/test_phase1_integration.py -v -s -m integration
"""

import pytest

from src.config import Config
from src.phases.phase1 import IntentionResponse, execute
from src.utils.llm import LLMClient
from src.utils.llm_adapters import OpenAIAdapter
from src.utils.storage import Simulation, load_simulation

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
def demo_sim(config: Config) -> Simulation:
    """Load demo simulation."""
    sim_path = config.project_root / "simulations" / "demo-sim"
    return load_simulation(sim_path)


class TestPhase1RealLLM:
    """Integration tests with real LLM calls."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_generate_intention_real_llm(self, config: Config, demo_sim: Simulation) -> None:
        """Actual intentions are generated from LLM for all characters.

        Verifies:
        - Phase 1 successfully calls the LLM
        - Returns valid IntentionResponse for each character
        - Intentions are non-empty strings (not idle)
        """
        # Create real LLM client with entities from simulation
        entities = [char.model_dump() for char in demo_sim.characters.values()]
        adapter = OpenAIAdapter(config.phase1)
        llm_client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=config.phase1.response_chain_depth,
        )

        # Execute Phase 1
        result = await execute(demo_sim, config, llm_client)

        # Verify result
        assert result.success is True

        # All characters should have intentions
        for char_id in demo_sim.characters:
            assert char_id in result.data, f"Missing intention for {char_id}"
            assert isinstance(result.data[char_id], IntentionResponse)
            assert len(result.data[char_id].intention) > 0
            assert result.data[char_id].intention != "idle"

        # Cleanup - delete any response chains
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
    async def test_intention_language_matches_simulation(
        self, config: Config, demo_sim: Simulation
    ) -> None:
        """Intentions are generated in Russian (simulation language).

        The demo-sim prompts are in Russian, so intentions should contain
        Cyrillic characters.
        """
        entities = [char.model_dump() for char in demo_sim.characters.values()]
        adapter = OpenAIAdapter(config.phase1)
        llm_client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=config.phase1.response_chain_depth,
        )

        result = await execute(demo_sim, config, llm_client)

        # Check that at least one intention contains Cyrillic
        has_cyrillic = False
        for intention_response in result.data.values():
            intention = intention_response.intention
            if any("\u0400" <= char <= "\u04ff" for char in intention):
                has_cyrillic = True
                break

        assert has_cyrillic, (
            "Expected at least one intention in Russian (Cyrillic). "
            f"Got: {[r.intention for r in result.data.values()]}"
        )

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

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_multiple_characters_unique_intentions(
        self, config: Config, demo_sim: Simulation
    ) -> None:
        """Different characters generate different intentions.

        Each character has unique context and should produce
        a unique intention.
        """
        entities = [char.model_dump() for char in demo_sim.characters.values()]
        adapter = OpenAIAdapter(config.phase1)
        llm_client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=config.phase1.response_chain_depth,
        )

        result = await execute(demo_sim, config, llm_client)

        # Collect all intentions
        intentions = [r.intention for r in result.data.values()]

        # All should be unique (no duplicates)
        assert len(intentions) == len(set(intentions)), (
            f"Expected unique intentions for each character, got duplicates: {intentions}"
        )

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
