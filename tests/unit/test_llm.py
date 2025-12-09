"""Unit tests for LLMClient with mocked adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from src.utils.llm import (
    BatchStats,
    LLMClient,
    LLMRequest,
    RequestResult,
    ResponseChainManager,
)
from src.utils.llm_adapters.base import (
    AdapterResponse,
    ResponseDebugInfo,
    ResponseUsage,
)
from src.utils.llm_errors import (
    LLMError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)


class SimpleAnswer(BaseModel):
    """Simple test schema."""

    answer: str


class ComplexResponse(BaseModel):
    """Complex test schema with nested fields."""

    steps: list[str]
    final_answer: str
    confidence: float


@pytest.fixture
def mock_adapter() -> MagicMock:
    """Create mock adapter with async methods."""
    adapter = MagicMock()
    adapter.execute = AsyncMock()
    adapter.delete_response = AsyncMock(return_value=True)
    return adapter


def make_adapter_response(
    response_id: str = "resp_test123",
    answer: str = "42",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> AdapterResponse[SimpleAnswer]:
    """Create AdapterResponse with SimpleAnswer."""
    return AdapterResponse(
        response_id=response_id,
        parsed=SimpleAnswer(answer=answer),
        usage=ResponseUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=0,
            cached_tokens=0,
            total_tokens=input_tokens + output_tokens,
        ),
        debug=ResponseDebugInfo(
            model="test-model",
            created_at=1234567890,
            service_tier=None,
            reasoning_summary=None,
        ),
    )


def make_complex_response(
    response_id: str = "resp_complex123",
    steps: list[str] | None = None,
    final_answer: str = "result",
    confidence: float = 0.95,
) -> AdapterResponse[ComplexResponse]:
    """Create AdapterResponse with ComplexResponse."""
    if steps is None:
        steps = ["step1", "step2"]
    return AdapterResponse(
        response_id=response_id,
        parsed=ComplexResponse(steps=steps, final_answer=final_answer, confidence=confidence),
        usage=ResponseUsage(
            input_tokens=200,
            output_tokens=100,
            reasoning_tokens=50,
            cached_tokens=0,
            total_tokens=300,
        ),
        debug=ResponseDebugInfo(
            model="test-reasoning-model",
            created_at=1234567890,
            service_tier="default",
            reasoning_summary=["Thinking..."],
        ),
    )


# =============================================================================
# ResponseChainManager Tests
# =============================================================================


class TestResponseChainManagerInit:
    """Tests for ResponseChainManager initialization."""

    def test_init_indexes_entities(self) -> None:
        """Entities are indexed by identity.id."""
        entities = [
            {"identity": {"id": "alice"}, "state": {}},
            {"identity": {"id": "bob"}, "state": {}},
        ]
        manager = ResponseChainManager(entities)

        assert "alice" in manager.entities
        assert "bob" in manager.entities
        assert manager.entities["alice"] is entities[0]
        assert manager.entities["bob"] is entities[1]

    def test_init_skips_entities_without_id(self) -> None:
        """Entities without valid id are skipped."""
        entities = [
            {"identity": {"id": "valid"}, "state": {}},
            {"identity": {}, "state": {}},  # No id
            {"state": {}},  # No identity
            {"identity": None, "state": {}},  # None identity
        ]
        manager = ResponseChainManager(entities)

        assert len(manager.entities) == 1
        assert "valid" in manager.entities

    def test_init_empty_list(self) -> None:
        """Works with empty entity list."""
        manager = ResponseChainManager([])
        assert len(manager.entities) == 0

    def test_init_unicode_ids(self) -> None:
        """Works with non-ASCII entity IDs."""
        entities = [
            {"identity": {"id": "персонаж"}, "state": {}},
            {"identity": {"id": "日本語"}, "state": {}},
        ]
        manager = ResponseChainManager(entities)

        assert "персонаж" in manager.entities
        assert "日本語" in manager.entities


class TestResponseChainManagerGetPrevious:
    """Tests for get_previous method."""

    def test_get_previous_empty_chain(self) -> None:
        """Returns None for empty chain."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        manager = ResponseChainManager(entities)

        result = manager.get_previous("intention:bob")
        assert result is None

    def test_get_previous_with_chain(self) -> None:
        """Returns last response_id from chain."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {
                    "intention_chain": ["resp_1", "resp_2", "resp_3"],
                },
            }
        ]
        manager = ResponseChainManager(entities)

        result = manager.get_previous("intention:bob")
        assert result == "resp_3"

    def test_get_previous_unknown_entity(self) -> None:
        """Returns None for unknown entity."""
        entities = [{"identity": {"id": "alice"}, "state": {}}]
        manager = ResponseChainManager(entities)

        result = manager.get_previous("intention:unknown")
        assert result is None

    def test_get_previous_different_chains(self) -> None:
        """Returns correct chain for each type."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {
                    "intention_chain": ["resp_int_1"],
                    "memory_chain": ["resp_mem_1", "resp_mem_2"],
                },
            }
        ]
        manager = ResponseChainManager(entities)

        assert manager.get_previous("intention:bob") == "resp_int_1"
        assert manager.get_previous("memory:bob") == "resp_mem_2"

    def test_get_previous_no_openai_section(self) -> None:
        """Returns None when _openai section missing."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        manager = ResponseChainManager(entities)

        result = manager.get_previous("intention:bob")
        assert result is None


class TestResponseChainManagerConfirm:
    """Tests for confirm method."""

    def test_confirm_depth_zero(self) -> None:
        """Depth 0 returns None and doesn't mutate."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        manager = ResponseChainManager(entities)

        result = manager.confirm("intention:bob", "resp_123", depth=0)

        assert result is None
        assert "_openai" not in entities[0]

    def test_confirm_creates_openai_section(self) -> None:
        """Creates _openai section if missing."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        manager = ResponseChainManager(entities)

        manager.confirm("intention:bob", "resp_123", depth=2)

        assert "_openai" in entities[0]
        assert "intention_chain" in entities[0]["_openai"]

    def test_confirm_creates_chain(self) -> None:
        """Creates chain if missing."""
        entities = [{"identity": {"id": "bob"}, "state": {}, "_openai": {}}]
        manager = ResponseChainManager(entities)

        manager.confirm("memory:bob", "resp_123", depth=2)

        assert "memory_chain" in entities[0]["_openai"]
        assert entities[0]["_openai"]["memory_chain"] == ["resp_123"]

    def test_confirm_appends_to_chain(self) -> None:
        """Appends response_id to existing chain."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {"intention_chain": ["resp_1"]},
            }
        ]
        manager = ResponseChainManager(entities)

        result = manager.confirm("intention:bob", "resp_2", depth=3)

        assert result is None
        assert entities[0]["_openai"]["intention_chain"] == ["resp_1", "resp_2"]

    def test_confirm_sliding_window_evicts(self) -> None:
        """Evicts oldest when chain reaches depth."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {"intention_chain": ["resp_1", "resp_2"]},
            }
        ]
        manager = ResponseChainManager(entities)

        evicted = manager.confirm("intention:bob", "resp_3", depth=2)

        assert evicted == "resp_1"
        assert entities[0]["_openai"]["intention_chain"] == ["resp_2", "resp_3"]

    def test_confirm_unknown_entity(self) -> None:
        """Returns None for unknown entity."""
        entities = [{"identity": {"id": "alice"}, "state": {}}]
        manager = ResponseChainManager(entities)

        result = manager.confirm("intention:unknown", "resp_123", depth=2)
        assert result is None

    def test_confirm_depth_one(self) -> None:
        """Depth 1 keeps only latest response."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {"intention_chain": ["resp_old"]},
            }
        ]
        manager = ResponseChainManager(entities)

        evicted = manager.confirm("intention:bob", "resp_new", depth=1)

        assert evicted == "resp_old"
        assert entities[0]["_openai"]["intention_chain"] == ["resp_new"]


class TestResponseChainManagerParseKey:
    """Tests for _parse_key method."""

    def test_parse_key_intention(self) -> None:
        """Parses intention key correctly."""
        manager = ResponseChainManager([])
        entity_id, chain_name = manager._parse_key("intention:bob")

        assert entity_id == "bob"
        assert chain_name == "intention"

    def test_parse_key_memory(self) -> None:
        """Parses memory key correctly."""
        manager = ResponseChainManager([])
        entity_id, chain_name = manager._parse_key("memory:elvira")

        assert entity_id == "elvira"
        assert chain_name == "memory"

    def test_parse_key_resolution(self) -> None:
        """Parses resolution key correctly."""
        manager = ResponseChainManager([])
        entity_id, chain_name = manager._parse_key("resolution:tavern")

        assert entity_id == "tavern"
        assert chain_name == "resolution"

    def test_parse_key_with_colon_in_id(self) -> None:
        """Handles entity IDs containing colons."""
        manager = ResponseChainManager([])
        entity_id, chain_name = manager._parse_key("intention:entity:with:colons")

        assert entity_id == "entity:with:colons"
        assert chain_name == "intention"


# =============================================================================
# LLMClient Initialization Tests
# =============================================================================


class TestLLMClientInit:
    """Tests for LLMClient initialization."""

    def test_client_stores_adapter(self, mock_adapter: MagicMock) -> None:
        """Adapter is stored in client."""
        client = LLMClient(mock_adapter, [], default_depth=0)
        assert client.adapter is mock_adapter

    def test_client_creates_chain_manager(self, mock_adapter: MagicMock) -> None:
        """Chain manager is created with entities."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        client = LLMClient(mock_adapter, entities, default_depth=2)

        assert isinstance(client.chain_manager, ResponseChainManager)
        assert "bob" in client.chain_manager.entities

    def test_client_stores_default_depth(self, mock_adapter: MagicMock) -> None:
        """Default depth is stored."""
        client = LLMClient(mock_adapter, [], default_depth=5)
        assert client.default_depth == 5

    def test_client_empty_entities(self, mock_adapter: MagicMock) -> None:
        """Works with empty entity list."""
        client = LLMClient(mock_adapter, [], default_depth=0)
        assert len(client.chain_manager.entities) == 0


# =============================================================================
# LLMClient.create_response Tests
# =============================================================================


class TestLLMClientCreateResponse:
    """Tests for create_response method."""

    @pytest.mark.asyncio
    async def test_create_response_success(self, mock_adapter: MagicMock) -> None:
        """Returns parsed model on success."""
        mock_adapter.execute.return_value = make_adapter_response(answer="success")
        client = LLMClient(mock_adapter, [], default_depth=0)

        result = await client.create_response(
            instructions="Test",
            input_data="Test input",
            schema=SimpleAnswer,
        )

        assert isinstance(result, SimpleAnswer)
        assert result.answer == "success"

    @pytest.mark.asyncio
    async def test_create_response_uses_chain(self, mock_adapter: MagicMock) -> None:
        """Uses previous_response_id from chain."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {"intention_chain": ["resp_prev"]},
            }
        ]
        mock_adapter.execute.return_value = make_adapter_response()
        client = LLMClient(mock_adapter, entities, default_depth=2)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )

        call_kwargs = mock_adapter.execute.call_args.kwargs
        assert call_kwargs["previous_response_id"] == "resp_prev"

    @pytest.mark.asyncio
    async def test_create_response_confirms(self, mock_adapter: MagicMock) -> None:
        """Confirms response with default_depth."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        mock_adapter.execute.return_value = make_adapter_response(response_id="resp_new")
        client = LLMClient(mock_adapter, entities, default_depth=2)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )

        chain = entities[0]["_openai"]["intention_chain"]
        assert "resp_new" in chain

    @pytest.mark.asyncio
    async def test_create_response_accumulates_usage(self, mock_adapter: MagicMock) -> None:
        """Accumulates usage in entity."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        mock_adapter.execute.return_value = make_adapter_response(
            input_tokens=100, output_tokens=50
        )
        client = LLMClient(mock_adapter, entities, default_depth=1)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )

        usage = entities[0]["_openai"]["usage"]
        assert usage["total_tokens"] == 150  # input + output
        assert usage["reasoning_tokens"] == 0
        assert usage["cached_tokens"] == 0
        assert usage["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_create_response_without_entity_key(self, mock_adapter: MagicMock) -> None:
        """No chain interaction without entity_key."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        mock_adapter.execute.return_value = make_adapter_response()
        client = LLMClient(mock_adapter, entities, default_depth=2)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
            entity_key=None,  # No entity key
        )

        # No previous_response_id should be passed
        call_kwargs = mock_adapter.execute.call_args.kwargs
        assert call_kwargs["previous_response_id"] is None

        # No chain should be created
        assert "_openai" not in entities[0]

    @pytest.mark.asyncio
    async def test_create_response_propagates_refusal(self, mock_adapter: MagicMock) -> None:
        """Propagates LLMRefusalError from adapter."""
        mock_adapter.execute.side_effect = LLMRefusalError("Refused content")
        client = LLMClient(mock_adapter, [], default_depth=0)

        with pytest.raises(LLMRefusalError) as exc_info:
            await client.create_response(
                instructions="Test",
                input_data="Bad content",
                schema=SimpleAnswer,
            )

        assert exc_info.value.refusal_message == "Refused content"

    @pytest.mark.asyncio
    async def test_create_response_propagates_timeout(self, mock_adapter: MagicMock) -> None:
        """Propagates LLMTimeoutError from adapter."""
        mock_adapter.execute.side_effect = LLMTimeoutError("Timeout after 3 attempts")
        client = LLMClient(mock_adapter, [], default_depth=0)

        with pytest.raises(LLMTimeoutError):
            await client.create_response(
                instructions="Test",
                input_data="Test",
                schema=SimpleAnswer,
            )

    @pytest.mark.asyncio
    async def test_create_response_deletes_evicted(self, mock_adapter: MagicMock) -> None:
        """Deletes evicted response from chain."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {"intention_chain": ["resp_old"]},
            }
        ]
        mock_adapter.execute.return_value = make_adapter_response(response_id="resp_new")
        client = LLMClient(mock_adapter, entities, default_depth=1)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )

        mock_adapter.delete_response.assert_called_once_with("resp_old")


# =============================================================================
# LLMClient.create_batch Tests
# =============================================================================


class TestLLMClientCreateBatch:
    """Tests for create_batch method."""

    @pytest.mark.asyncio
    async def test_batch_empty_list(self, mock_adapter: MagicMock) -> None:
        """Empty batch returns empty list."""
        client = LLMClient(mock_adapter, [], default_depth=0)

        results = await client.create_batch([])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_all_success(self, mock_adapter: MagicMock) -> None:
        """All successful requests return parsed models."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(response_id="r1", answer="first"),
            make_adapter_response(response_id="r2", answer="second"),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(instructions="Q1", input_data="D1", schema=SimpleAnswer, entity_key=None),
            LLMRequest(instructions="Q2", input_data="D2", schema=SimpleAnswer, entity_key=None),
        ]

        results = await client.create_batch(requests)

        assert len(results) == 2
        assert all(isinstance(r, SimpleAnswer) for r in results)
        assert results[0].answer == "first"
        assert results[1].answer == "second"

    @pytest.mark.asyncio
    async def test_batch_preserves_order(self, mock_adapter: MagicMock) -> None:
        """Results are in same order as requests."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(answer="A"),
            make_adapter_response(answer="B"),
            make_adapter_response(answer="C"),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(instructions="1", input_data="1", schema=SimpleAnswer),
            LLMRequest(instructions="2", input_data="2", schema=SimpleAnswer),
            LLMRequest(instructions="3", input_data="3", schema=SimpleAnswer),
        ]

        results = await client.create_batch(requests)

        assert [r.answer for r in results] == ["A", "B", "C"]

    @pytest.mark.asyncio
    async def test_batch_partial_failure(self, mock_adapter: MagicMock) -> None:
        """Mix of success and failure in results."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(answer="success"),
            LLMRateLimitError("Rate limited"),
            make_adapter_response(answer="also success"),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(instructions="1", input_data="1", schema=SimpleAnswer),
            LLMRequest(instructions="2", input_data="2", schema=SimpleAnswer),
            LLMRequest(instructions="3", input_data="3", schema=SimpleAnswer),
        ]

        results = await client.create_batch(requests)

        assert len(results) == 3
        assert isinstance(results[0], SimpleAnswer)
        assert isinstance(results[1], LLMRateLimitError)
        assert isinstance(results[2], SimpleAnswer)

    @pytest.mark.asyncio
    async def test_batch_all_failure(self, mock_adapter: MagicMock) -> None:
        """All failed requests return LLMError."""
        mock_adapter.execute.side_effect = [
            LLMTimeoutError("Timeout 1"),
            LLMRefusalError("Refused"),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(instructions="1", input_data="1", schema=SimpleAnswer),
            LLMRequest(instructions="2", input_data="2", schema=SimpleAnswer),
        ]

        results = await client.create_batch(requests)

        assert len(results) == 2
        assert isinstance(results[0], LLMTimeoutError)
        assert isinstance(results[1], LLMRefusalError)

    @pytest.mark.asyncio
    async def test_batch_uses_previous_response_id(self, mock_adapter: MagicMock) -> None:
        """Batch requests use previous_response_id from chain."""
        entities = [
            {
                "identity": {"id": "alice"},
                "state": {},
                "_openai": {"intention_chain": ["resp_alice_prev"]},
            },
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {"intention_chain": ["resp_bob_prev"]},
            },
        ]
        mock_adapter.execute.side_effect = [
            make_adapter_response(response_id="r_alice"),
            make_adapter_response(response_id="r_bob"),
        ]
        client = LLMClient(mock_adapter, entities, default_depth=2)

        requests = [
            LLMRequest(
                instructions="A",
                input_data="A",
                schema=SimpleAnswer,
                entity_key="intention:alice",
            ),
            LLMRequest(
                instructions="B",
                input_data="B",
                schema=SimpleAnswer,
                entity_key="intention:bob",
            ),
        ]

        await client.create_batch(requests)

        # Check both calls used correct previous_response_id
        calls = mock_adapter.execute.call_args_list
        prev_ids = [c.kwargs["previous_response_id"] for c in calls]
        assert "resp_alice_prev" in prev_ids
        assert "resp_bob_prev" in prev_ids

    @pytest.mark.asyncio
    async def test_batch_confirms_with_depth_override(self, mock_adapter: MagicMock) -> None:
        """Batch respects depth_override in request."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {"intention_chain": ["r1", "r2"]},
            }
        ]
        mock_adapter.execute.return_value = make_adapter_response(response_id="r3")
        client = LLMClient(mock_adapter, entities, default_depth=5)

        requests = [
            LLMRequest(
                instructions="Test",
                input_data="Test",
                schema=SimpleAnswer,
                entity_key="intention:bob",
                depth_override=2,  # Override to 2, should evict
            ),
        ]

        await client.create_batch(requests)

        # Chain should be ["r2", "r3"] after eviction
        chain = entities[0]["_openai"]["intention_chain"]
        assert chain == ["r2", "r3"]
        mock_adapter.delete_response.assert_called_once_with("r1")

    @pytest.mark.asyncio
    async def test_batch_confirms_with_default_depth(self, mock_adapter: MagicMock) -> None:
        """Batch uses default_depth when no override."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        mock_adapter.execute.return_value = make_adapter_response(response_id="r1")
        client = LLMClient(mock_adapter, entities, default_depth=3)

        requests = [
            LLMRequest(
                instructions="Test",
                input_data="Test",
                schema=SimpleAnswer,
                entity_key="intention:bob",
                # No depth_override
            ),
        ]

        await client.create_batch(requests)

        # Chain should have 1 element
        chain = entities[0]["_openai"]["intention_chain"]
        assert chain == ["r1"]

    @pytest.mark.asyncio
    async def test_batch_deletes_evicted(self, mock_adapter: MagicMock) -> None:
        """Batch deletes evicted responses."""
        entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {"intention_chain": ["old_resp"]},
            }
        ]
        mock_adapter.execute.return_value = make_adapter_response(response_id="new_resp")
        client = LLMClient(mock_adapter, entities, default_depth=1)

        requests = [
            LLMRequest(
                instructions="Test",
                input_data="Test",
                schema=SimpleAnswer,
                entity_key="intention:bob",
            ),
        ]

        await client.create_batch(requests)

        mock_adapter.delete_response.assert_called_once_with("old_resp")

    @pytest.mark.asyncio
    async def test_batch_accumulates_usage_per_entity(self, mock_adapter: MagicMock) -> None:
        """Usage accumulated separately per entity."""
        entities = [
            {"identity": {"id": "alice"}, "state": {}},
            {"identity": {"id": "bob"}, "state": {}},
        ]
        mock_adapter.execute.side_effect = [
            make_adapter_response(input_tokens=100, output_tokens=50),
            make_adapter_response(input_tokens=200, output_tokens=100),
        ]
        client = LLMClient(mock_adapter, entities, default_depth=1)

        requests = [
            LLMRequest(
                instructions="A",
                input_data="A",
                schema=SimpleAnswer,
                entity_key="intention:alice",
            ),
            LLMRequest(
                instructions="B",
                input_data="B",
                schema=SimpleAnswer,
                entity_key="intention:bob",
            ),
        ]

        await client.create_batch(requests)

        alice_usage = entities[0]["_openai"]["usage"]
        bob_usage = entities[1]["_openai"]["usage"]

        assert alice_usage["total_tokens"] == 150  # 100 + 50
        assert bob_usage["total_tokens"] == 300  # 200 + 100

    @pytest.mark.asyncio
    async def test_batch_wraps_unexpected_exceptions(self, mock_adapter: MagicMock) -> None:
        """Unexpected exceptions wrapped in LLMError."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(answer="ok"),
            ValueError("Unexpected error"),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(instructions="1", input_data="1", schema=SimpleAnswer),
            LLMRequest(instructions="2", input_data="2", schema=SimpleAnswer),
        ]

        results = await client.create_batch(requests)

        assert isinstance(results[0], SimpleAnswer)
        assert isinstance(results[1], LLMError)
        assert "Unexpected error" in str(results[1])


# =============================================================================
# Usage Accumulation Tests
# =============================================================================


class TestUsageAccumulation:
    """Tests for usage accumulation."""

    @pytest.mark.asyncio
    async def test_accumulate_creates_openai_section(self, mock_adapter: MagicMock) -> None:
        """Creates _openai section if missing."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        mock_adapter.execute.return_value = make_adapter_response()
        client = LLMClient(mock_adapter, entities, default_depth=1)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )

        assert "_openai" in entities[0]

    @pytest.mark.asyncio
    async def test_accumulate_creates_usage_section(self, mock_adapter: MagicMock) -> None:
        """Creates usage section if missing."""
        entities = [{"identity": {"id": "bob"}, "state": {}, "_openai": {}}]
        mock_adapter.execute.return_value = make_adapter_response()
        client = LLMClient(mock_adapter, entities, default_depth=1)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )

        assert "usage" in entities[0]["_openai"]

    @pytest.mark.asyncio
    async def test_accumulate_increments_counters(self, mock_adapter: MagicMock) -> None:
        """Increments all usage counters."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        mock_adapter.execute.return_value = make_adapter_response(
            input_tokens=150, output_tokens=75
        )
        client = LLMClient(mock_adapter, entities, default_depth=1)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )

        usage = entities[0]["_openai"]["usage"]
        assert usage["total_tokens"] == 225  # 150 + 75
        assert usage["reasoning_tokens"] == 0
        assert usage["cached_tokens"] == 0
        assert usage["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_accumulate_multiple_requests_sum(self, mock_adapter: MagicMock) -> None:
        """Multiple requests sum correctly."""
        entities = [{"identity": {"id": "bob"}, "state": {}}]
        mock_adapter.execute.side_effect = [
            make_adapter_response(response_id="r1", input_tokens=100, output_tokens=50),
            make_adapter_response(response_id="r2", input_tokens=200, output_tokens=100),
        ]
        client = LLMClient(mock_adapter, entities, default_depth=5)

        await client.create_response(
            instructions="Test1",
            input_data="Test1",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )
        await client.create_response(
            instructions="Test2",
            input_data="Test2",
            schema=SimpleAnswer,
            entity_key="intention:bob",
        )

        usage = entities[0]["_openai"]["usage"]
        assert usage["total_tokens"] == 450  # (100+50) + (200+100)
        assert usage["total_requests"] == 2


# =============================================================================
# LLMRequest Tests
# =============================================================================


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_request_defaults(self) -> None:
        """Default values are correct."""
        request = LLMRequest(
            instructions="Test",
            input_data="Data",
            schema=SimpleAnswer,
        )

        assert request.entity_key is None
        assert request.depth_override is None

    def test_request_with_override(self) -> None:
        """Depth override is stored."""
        request = LLMRequest(
            instructions="Test",
            input_data="Data",
            schema=SimpleAnswer,
            entity_key="intention:bob",
            depth_override=5,
        )

        assert request.entity_key == "intention:bob"
        assert request.depth_override == 5

    def test_request_stores_schema(self) -> None:
        """Schema type is stored correctly."""
        request = LLMRequest(
            instructions="Test",
            input_data="Data",
            schema=ComplexResponse,
        )

        assert request.schema is ComplexResponse


# =============================================================================
# BatchStats Tests
# =============================================================================


class TestBatchStats:
    """Tests for BatchStats dataclass and get_last_batch_stats()."""

    @pytest.mark.asyncio
    async def test_get_last_batch_stats_after_batch(self, mock_adapter: MagicMock) -> None:
        """Batch stats are correct after create_batch()."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(input_tokens=100, output_tokens=50),
            make_adapter_response(input_tokens=200, output_tokens=100),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(instructions="A", input_data="A", schema=SimpleAnswer),
            LLMRequest(instructions="B", input_data="B", schema=SimpleAnswer),
        ]

        await client.create_batch(requests)

        stats = client.get_last_batch_stats()
        assert stats.total_tokens == 450  # (100+50) + (200+100)
        assert stats.reasoning_tokens == 0
        assert stats.cached_tokens == 0
        assert stats.request_count == 2
        assert stats.success_count == 2
        assert stats.error_count == 0

    @pytest.mark.asyncio
    async def test_get_last_batch_stats_after_single(self, mock_adapter: MagicMock) -> None:
        """Batch stats are correct after create_response()."""
        mock_adapter.execute.return_value = make_adapter_response(
            input_tokens=100, output_tokens=50
        )
        client = LLMClient(mock_adapter, [], default_depth=0)

        await client.create_response(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
        )

        stats = client.get_last_batch_stats()
        assert stats.total_tokens == 150
        assert stats.request_count == 1
        assert stats.success_count == 1
        assert stats.error_count == 0

    @pytest.mark.asyncio
    async def test_get_last_batch_stats_with_errors(self, mock_adapter: MagicMock) -> None:
        """Error count is tracked in batch stats."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(input_tokens=100, output_tokens=50),
            LLMTimeoutError("Timeout"),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(instructions="A", input_data="A", schema=SimpleAnswer),
            LLMRequest(instructions="B", input_data="B", schema=SimpleAnswer),
        ]

        await client.create_batch(requests)

        stats = client.get_last_batch_stats()
        assert stats.total_tokens == 150  # Only successful request counted
        assert stats.request_count == 2
        assert stats.success_count == 1
        assert stats.error_count == 1

    @pytest.mark.asyncio
    async def test_batch_stats_reset_between_calls(self, mock_adapter: MagicMock) -> None:
        """Stats are reset at start of each create_batch() call."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(input_tokens=100, output_tokens=50),
            make_adapter_response(input_tokens=200, output_tokens=100),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        # First batch
        await client.create_batch(
            [
                LLMRequest(instructions="A", input_data="A", schema=SimpleAnswer),
            ]
        )
        stats1 = client.get_last_batch_stats()
        assert stats1.total_tokens == 150

        # Second batch - stats should be reset, not accumulated
        await client.create_batch(
            [
                LLMRequest(instructions="B", input_data="B", schema=SimpleAnswer),
            ]
        )
        stats2 = client.get_last_batch_stats()
        assert stats2.total_tokens == 300  # Only second batch, not 150+300

    def test_batch_stats_defaults(self) -> None:
        """BatchStats has correct default values."""
        stats = BatchStats()
        assert stats.total_tokens == 0
        assert stats.reasoning_tokens == 0
        assert stats.cached_tokens == 0
        assert stats.request_count == 0
        assert stats.success_count == 0
        assert stats.error_count == 0
        assert stats.results == []

    def test_batch_stats_results_default_empty(self) -> None:
        """BatchStats.results defaults to empty list."""
        stats = BatchStats()
        assert stats.results == []
        assert isinstance(stats.results, list)


# =============================================================================
# RequestResult Tests
# =============================================================================


class TestRequestResult:
    """Tests for RequestResult dataclass."""

    def test_request_result_success(self) -> None:
        """RequestResult captures successful request."""
        usage = ResponseUsage(
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=25,
            cached_tokens=10,
            total_tokens=150,
        )
        result = RequestResult(
            entity_key="intention:bob",
            success=True,
            usage=usage,
            reasoning_summary=["Thinking about intention..."],
        )

        assert result.entity_key == "intention:bob"
        assert result.success is True
        assert result.usage is usage
        assert result.reasoning_summary == ["Thinking about intention..."]
        assert result.error is None

    def test_request_result_failure(self) -> None:
        """RequestResult captures failed request."""
        result = RequestResult(
            entity_key="intention:alice",
            success=False,
            error="Rate limit exceeded",
        )

        assert result.entity_key == "intention:alice"
        assert result.success is False
        assert result.usage is None
        assert result.reasoning_summary is None
        assert result.error == "Rate limit exceeded"

    def test_request_result_without_entity_key(self) -> None:
        """RequestResult works without entity_key."""
        result = RequestResult(
            entity_key=None,
            success=True,
            usage=ResponseUsage(
                input_tokens=50,
                output_tokens=25,
                total_tokens=75,
            ),
        )

        assert result.entity_key is None
        assert result.success is True

    def test_request_result_non_ascii_error(self) -> None:
        """RequestResult handles non-ASCII error messages."""
        result = RequestResult(
            entity_key="intention:персонаж",
            success=False,
            error="Ошибка: превышен лимит запросов",
        )

        assert result.entity_key == "intention:персонаж"
        assert result.error == "Ошибка: превышен лимит запросов"


# =============================================================================
# BatchStats.results Integration Tests
# =============================================================================


class TestBatchStatsResults:
    """Tests for BatchStats.results population."""

    @pytest.mark.asyncio
    async def test_batch_stats_results_populated_on_success(self, mock_adapter: MagicMock) -> None:
        """BatchStats.results populated with RequestResult on success."""
        mock_adapter.execute.return_value = make_adapter_response(
            response_id="resp_1", answer="test"
        )
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(
                instructions="Test",
                input_data="Data",
                schema=SimpleAnswer,
                entity_key="intention:bob",
            ),
        ]

        await client.create_batch(requests)
        stats = client.get_last_batch_stats()

        assert len(stats.results) == 1
        result = stats.results[0]
        assert result.entity_key == "intention:bob"
        assert result.success is True
        assert result.usage is not None
        assert result.error is None

    @pytest.mark.asyncio
    async def test_batch_stats_results_populated_on_failure(self, mock_adapter: MagicMock) -> None:
        """BatchStats.results populated with RequestResult on failure."""
        mock_adapter.execute.side_effect = LLMTimeoutError("Request timed out")
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(
                instructions="Test",
                input_data="Data",
                schema=SimpleAnswer,
                entity_key="intention:alice",
            ),
        ]

        await client.create_batch(requests)
        stats = client.get_last_batch_stats()

        assert len(stats.results) == 1
        result = stats.results[0]
        assert result.entity_key == "intention:alice"
        assert result.success is False
        assert result.usage is None
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_batch_stats_results_contains_reasoning_summary(
        self, mock_adapter: MagicMock
    ) -> None:
        """BatchStats.results contains reasoning_summary from response."""
        mock_adapter.execute.return_value = make_complex_response()
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(
                instructions="Think",
                input_data="Hard problem",
                schema=ComplexResponse,
                entity_key="intention:bob",
            ),
        ]

        await client.create_batch(requests)
        stats = client.get_last_batch_stats()

        assert len(stats.results) == 1
        result = stats.results[0]
        assert result.reasoning_summary == ["Thinking..."]

    @pytest.mark.asyncio
    async def test_batch_stats_results_mixed_success_failure(self, mock_adapter: MagicMock) -> None:
        """BatchStats.results contains both success and failure results."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(answer="ok"),
            LLMRateLimitError("Rate limited"),
            make_adapter_response(answer="also ok"),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        requests = [
            LLMRequest(
                instructions="1",
                input_data="1",
                schema=SimpleAnswer,
                entity_key="intention:a",
            ),
            LLMRequest(
                instructions="2",
                input_data="2",
                schema=SimpleAnswer,
                entity_key="intention:b",
            ),
            LLMRequest(
                instructions="3",
                input_data="3",
                schema=SimpleAnswer,
                entity_key="intention:c",
            ),
        ]

        await client.create_batch(requests)
        stats = client.get_last_batch_stats()

        assert len(stats.results) == 3
        assert stats.results[0].success is True
        assert stats.results[0].entity_key == "intention:a"
        assert stats.results[1].success is False
        assert stats.results[1].entity_key == "intention:b"
        assert "rate" in stats.results[1].error.lower()
        assert stats.results[2].success is True
        assert stats.results[2].entity_key == "intention:c"

    @pytest.mark.asyncio
    async def test_create_response_populates_results(self, mock_adapter: MagicMock) -> None:
        """create_response() also populates BatchStats.results."""
        mock_adapter.execute.return_value = make_complex_response()
        client = LLMClient(mock_adapter, [], default_depth=0)

        await client.create_response(
            instructions="Test",
            input_data="Data",
            schema=ComplexResponse,
            entity_key="intention:bob",
        )

        stats = client.get_last_batch_stats()

        assert len(stats.results) == 1
        result = stats.results[0]
        assert result.entity_key == "intention:bob"
        assert result.success is True
        assert result.reasoning_summary == ["Thinking..."]

    @pytest.mark.asyncio
    async def test_batch_stats_results_reset_between_calls(self, mock_adapter: MagicMock) -> None:
        """BatchStats.results reset between create_batch() calls."""
        mock_adapter.execute.side_effect = [
            make_adapter_response(answer="first"),
            make_adapter_response(answer="second"),
        ]
        client = LLMClient(mock_adapter, [], default_depth=0)

        # First batch
        await client.create_batch(
            [LLMRequest(instructions="1", input_data="1", schema=SimpleAnswer)]
        )
        stats1 = client.get_last_batch_stats()
        assert len(stats1.results) == 1

        # Second batch - results should be reset
        await client.create_batch(
            [LLMRequest(instructions="2", input_data="2", schema=SimpleAnswer)]
        )
        stats2 = client.get_last_batch_stats()
        assert len(stats2.results) == 1  # Only second batch result
