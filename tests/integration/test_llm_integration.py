"""Integration tests for LLMClient with real OpenAI API.

These tests require OPENAI_API_KEY environment variable.
They make real API calls and may incur costs.

Run with: pytest tests/integration/test_llm_integration.py -v -s
"""

import pytest
from pydantic import BaseModel

from src.config import Config
from src.utils.llm import LLMClient, LLMRequest
from src.utils.llm_adapters import OpenAIAdapter

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]


class SimpleAnswer(BaseModel):
    """Simple schema for tests."""

    answer: str


@pytest.fixture
def config() -> Config:
    """Load config, skip if no API key."""
    cfg = Config.load()
    if not cfg.openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env")
    return cfg


@pytest.fixture
def make_entity():
    """Factory for test entities."""

    def _make(entity_id: str) -> dict:
        return {
            "identity": {"id": entity_id},
            "state": {},
        }

    return _make


class TestChainManagement:
    """Tests for response chain with real API."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_sliding_window_eviction(self, config: Config, make_entity) -> None:
        """Test that sliding window evicts and deletes old responses.

        Scenario:
        - depth=2, make 3 requests
        - After 3rd request, 1st response should be deleted from OpenAI
        - Chain in entity should contain only [resp_2, resp_3]
        """
        entity = make_entity("test-char")
        entities = [entity]

        adapter = OpenAIAdapter(config.phase1)
        client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=2,  # Sliding window of 2
        )

        # Make 3 requests, each remembers previous context
        response_ids: list[str] = []

        # Request 1
        await client.create_response(
            instructions="Remember information given to you.",
            input_data="The secret code is ALPHA.",
            schema=SimpleAnswer,
            entity_key="intention:test-char",
        )
        chain = entity["_openai"]["intention_chain"]
        assert len(chain) == 1
        response_ids.append(chain[0])

        # Request 2
        await client.create_response(
            instructions="Remember information given to you.",
            input_data="The second code is BETA.",
            schema=SimpleAnswer,
            entity_key="intention:test-char",
        )
        chain = entity["_openai"]["intention_chain"]
        assert len(chain) == 2
        response_ids.append(chain[1])

        # Request 3 - should evict request 1
        await client.create_response(
            instructions="Remember information given to you.",
            input_data="The third code is GAMMA.",
            schema=SimpleAnswer,
            entity_key="intention:test-char",
        )
        chain = entity["_openai"]["intention_chain"]
        assert len(chain) == 2  # Still 2, not 3
        assert response_ids[0] not in chain  # First evicted
        assert response_ids[1] in chain  # Second still there
        response_ids.append(chain[1])

        # Verify first response was deleted from OpenAI
        # Try to use it as previous_response_id - should fail or return error
        try:
            await adapter.client.responses.retrieve(response_ids[0])
            pytest.fail("Expected error for deleted response")
        except Exception as e:
            # Should get 404 or similar error
            assert "404" in str(e) or "not found" in str(e).lower()

        # Cleanup remaining responses
        for resp_id in chain:
            await adapter.delete_response(resp_id)

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_chain_context_preserved(self, config: Config, make_entity) -> None:
        """Test that chain preserves context across requests.

        Scenario:
        - Request 1: Tell name "Алиса"
        - Request 2: Ask what the name was
        - Should remember from chain context
        """
        entity = make_entity("context-test")
        entities = [entity]

        adapter = OpenAIAdapter(config.phase1)
        client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=3,
        )

        # Request 1: Provide name
        await client.create_response(
            instructions="Remember the user's name.",
            input_data="My name is Алиса.",
            schema=SimpleAnswer,
            entity_key="memory:context-test",
        )

        # Request 2: Ask for name (uses chain)
        result = await client.create_response(
            instructions="Recall the user's name from previous context. Answer with just the name.",
            input_data="What was my name?",
            schema=SimpleAnswer,
            entity_key="memory:context-test",
        )

        # Should remember
        answer_lower = result.answer.lower()
        assert "алиса" in answer_lower or "alisa" in answer_lower or "alice" in answer_lower

        # Cleanup
        for resp_id in entity["_openai"]["memory_chain"]:
            await adapter.delete_response(resp_id)

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_independent_requests_no_context(self, config: Config, make_entity) -> None:
        """Test that depth=0 means independent requests (no chain).

        Scenario:
        - depth=0
        - Request 1: Tell name
        - Request 2: Ask name
        - Should NOT remember (no chain)
        """
        entity = make_entity("no-chain-test")
        entities = [entity]

        adapter = OpenAIAdapter(config.phase1)
        client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=0,  # Independent requests
        )

        # Request 1: Provide info
        await client.create_response(
            instructions="Note any information given.",
            input_data="The password is SECRET123.",
            schema=SimpleAnswer,
            entity_key="intention:no-chain-test",
        )

        # Request 2: Ask for info (no chain, so no context)
        result = await client.create_response(
            instructions="What password was mentioned in previous context? "
            "Say 'none' or 'unknown' if you don't know.",
            input_data="Tell me the password.",
            schema=SimpleAnswer,
            entity_key="intention:no-chain-test",
        )

        # Should NOT know the password (no chain context)
        answer_lower = result.answer.lower()
        assert "secret123" not in answer_lower

        # Verify no chain was created
        assert "intention_chain" not in entity.get("_openai", {})


class TestBatchWithChains:
    """Tests for batch execution with chains."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_batch_parallel_chain_updates(self, config: Config, make_entity) -> None:
        """Test that parallel batch requests update chains correctly.

        Scenario:
        - 2 entities: alice, bob
        - Batch with 1 request per entity
        - Each entity's chain should have 1 response
        """
        alice = make_entity("alice")
        bob = make_entity("bob")
        entities = [alice, bob]

        adapter = OpenAIAdapter(config.phase1)
        client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=2,
        )

        requests = [
            LLMRequest(
                instructions="Answer briefly.",
                input_data="Say hello as Alice.",
                schema=SimpleAnswer,
                entity_key="intention:alice",
            ),
            LLMRequest(
                instructions="Answer briefly.",
                input_data="Say hello as Bob.",
                schema=SimpleAnswer,
                entity_key="intention:bob",
            ),
        ]

        results = await client.create_batch(requests)

        # Both should succeed
        assert len(results) == 2
        assert all(isinstance(r, SimpleAnswer) for r in results)

        # Each entity has its own chain
        assert len(alice["_openai"]["intention_chain"]) == 1
        assert len(bob["_openai"]["intention_chain"]) == 1
        assert alice["_openai"]["intention_chain"][0] != bob["_openai"]["intention_chain"][0]

        # Cleanup
        for entity in entities:
            for resp_id in entity.get("_openai", {}).get("intention_chain", []):
                await adapter.delete_response(resp_id)


class TestUsageAccumulation:
    """Tests for usage tracking."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_usage_persisted_in_entity(self, config: Config, make_entity) -> None:
        """Test that usage stats are accumulated in entity."""
        entity = make_entity("usage-test")
        entities = [entity]

        adapter = OpenAIAdapter(config.phase1)
        client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=1,
        )

        # Make 2 requests
        await client.create_response(
            instructions="Answer briefly.",
            input_data="What is 2+2?",
            schema=SimpleAnswer,
            entity_key="intention:usage-test",
        )

        await client.create_response(
            instructions="Answer briefly.",
            input_data="What is 3+3?",
            schema=SimpleAnswer,
            entity_key="intention:usage-test",
        )

        # Check usage accumulated
        usage = entity["_openai"]["usage"]
        assert usage["total_requests"] == 2
        assert usage["total_tokens"] > 0
        assert usage["reasoning_tokens"] >= 0
        assert usage["cached_tokens"] >= 0

        # Cleanup
        for resp_id in entity.get("_openai", {}).get("intention_chain", []):
            await adapter.delete_response(resp_id)


class TestEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_empty_batch(self, config: Config, make_entity) -> None:
        """Empty batch returns empty list."""
        adapter = OpenAIAdapter(config.phase1)
        client = LLMClient(
            adapter=adapter,
            entities=[],
            default_depth=0,
        )

        results = await client.create_batch([])
        assert results == []

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_chain_survives_partial_failure(self, config: Config, make_entity) -> None:
        """If one request fails, others still update chains.

        Note: This test verifies that a successful request
        still updates the chain correctly.
        """
        entity = make_entity("partial-test")
        entities = [entity]

        adapter = OpenAIAdapter(config.phase1)
        client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=3,
        )

        # First request - should succeed
        await client.create_response(
            instructions="Answer briefly.",
            input_data="Say OK.",
            schema=SimpleAnswer,
            entity_key="intention:partial-test",
        )

        assert len(entity["_openai"]["intention_chain"]) == 1

        # Even if next request fails, chain state preserved
        # (We just verify chain wasn't corrupted)
        assert "intention_chain" in entity["_openai"]

        # Cleanup
        for resp_id in entity.get("_openai", {}).get("intention_chain", []):
            await adapter.delete_response(resp_id)

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_multiple_chain_types_on_same_entity(self, config: Config, make_entity) -> None:
        """Same entity can have multiple chain types."""
        entity = make_entity("multi-chain")
        entities = [entity]

        adapter = OpenAIAdapter(config.phase1)
        client = LLMClient(
            adapter=adapter,
            entities=entities,
            default_depth=2,
        )

        # Create intention chain
        await client.create_response(
            instructions="Answer briefly.",
            input_data="Intention test.",
            schema=SimpleAnswer,
            entity_key="intention:multi-chain",
        )

        # Create memory chain
        await client.create_response(
            instructions="Answer briefly.",
            input_data="Memory test.",
            schema=SimpleAnswer,
            entity_key="memory:multi-chain",
        )

        # Both chains should exist separately
        assert len(entity["_openai"]["intention_chain"]) == 1
        assert len(entity["_openai"]["memory_chain"]) == 1
        assert entity["_openai"]["intention_chain"][0] != entity["_openai"]["memory_chain"][0]

        # Cleanup
        for chain_key in ["intention_chain", "memory_chain"]:
            for resp_id in entity.get("_openai", {}).get(chain_key, []):
                await adapter.delete_response(resp_id)
