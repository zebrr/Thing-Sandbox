# TS-A.5c-LLM-001: LLM Client Implementation

## References

Read before starting:
- `docs/specs/util_llm.md` — main specification for this task
- `docs/specs/util_llm_adapter_openai.md` — adapter spec (already implemented)
- `docs/specs/util_llm_errors.md` — error hierarchy (already implemented)
- `docs/Thing' Sandbox LLM Approach v2.md` — conceptual document
- `src/utils/llm_adapters/openai.py` — existing adapter implementation
- `src/utils/llm_adapters/base.py` — AdapterResponse, ResponseUsage
- `src/utils/llm_errors.py` — LLMError hierarchy

## Context

We have completed:
- A.5a: PhaseConfig with response_chain_depth field
- A.5b: OpenAIAdapter with execute(), delete_response()

Now we implement LLMClient — provider-agnostic facade that phases will use.
This is the final piece of LLM infrastructure before vertical slice development.

### Architecture Overview

```
Phases (phase1.py, phase2a.py, etc.)
    │
    ▼
LLMClient (this task)
    │  - batch execution via asyncio.gather()
    │  - response chain management
    │  - usage accumulation
    │
    ▼
OpenAIAdapter (existing)
    │  - OpenAI API calls
    │  - retry logic
    │
    ▼
OpenAI API
```

## Steps

### Step 1: Create src/utils/llm.py

Implement three classes:

#### 1.1 LLMRequest dataclass

```python
@dataclass
class LLMRequest:
    """Request data for batch execution."""
    instructions: str
    input_data: str
    schema: type[BaseModel]
    entity_key: str | None = None
    depth_override: int | None = None
```

#### 1.2 ResponseChainManager class

Stateless helper for managing response chains in entities.

```python
class ResponseChainManager:
    """
    Manages response chains stored in entities.
    
    Entity key format: "{chain_type}:{entity_id}"
    Examples: "intention:bob", "memory:elvira", "resolution:tavern"
    
    Chain storage in entity:
    {
        "_openai": {
            "intention_chain": ["resp_abc", "resp_def"],
            "memory_chain": ["resp_xyz"],
            ...
        }
    }
    """
    
    def __init__(self, entities: list[dict]) -> None:
        """
        Build index of entities by ID.
        Each entity must have identity.id field.
        Skip entities without valid ID.
        """
        ...
    
    def get_previous(self, entity_key: str) -> str | None:
        """
        Get last response_id from chain.
        
        Parse entity_key → (entity_id, chain_name)
        Look up entity["_openai"]["{chain_name}_chain"][-1]
        Return None if chain empty or entity not found.
        """
        ...
    
    def confirm(
        self,
        entity_key: str,
        response_id: str,
        depth: int,
    ) -> str | None:
        """
        Add response to chain with sliding window.
        
        If depth == 0: return None (independent requests, no chain)
        
        Otherwise:
        - Ensure entity["_openai"]["{chain_name}_chain"] exists
        - If len(chain) >= depth: pop(0) → evicted
        - Append response_id
        - Return evicted or None
        
        Mutates entity in-place.
        """
        ...
    
    def _parse_key(self, entity_key: str) -> tuple[str, str]:
        """
        Parse "intention:bob" → ("bob", "intention")
        Parse "memory:elvira" → ("elvira", "memory")
        """
        chain_name, entity_id = entity_key.split(":", 1)
        return entity_id, chain_name
```

#### 1.3 LLMClient class

```python
class LLMClient:
    """
    Provider-agnostic facade for LLM requests.
    Created per-phase with corresponding adapter and entities.
    """
    
    def __init__(
        self,
        adapter: OpenAIAdapter,
        entities: list[dict],
        default_depth: int = 0,
    ) -> None:
        """
        Store adapter, create chain_manager, store default_depth.
        """
        ...
    
    async def create_response(
        self,
        instructions: str,
        input_data: str,
        schema: type[T],
        entity_key: str | None = None,
    ) -> T:
        """
        Single request to LLM.
        
        1. Get previous_response_id from chain (if entity_key)
        2. Execute via adapter
        3. Auto-confirm with default_depth
        4. Accumulate usage
        5. Return parsed response
        
        Exceptions propagate to caller.
        """
        ...
    
    async def create_batch(
        self,
        requests: list[LLMRequest],
    ) -> list[T | LLMError]:
        """
        Batch of parallel requests.
        
        1. Create tasks for all requests
        2. await asyncio.gather(*tasks, return_exceptions=True)
        3. Convert results: success → parsed, exception → LLMError
        4. Return list in same order as requests
        """
        ...
    
    async def _execute_one(self, request: LLMRequest) -> AdapterResponse:
        """
        Execute single request with chain and usage handling.
        
        1. Get previous_id from chain
        2. Execute via adapter
        3. Auto-confirm with depth (request.depth_override or self.default_depth)
        4. Delete evicted response if any
        5. Accumulate usage
        6. Return AdapterResponse
        """
        ...
    
    def _accumulate_usage(self, entity_key: str, usage: ResponseUsage) -> None:
        """
        Add usage stats to entity["_openai"]["usage"].
        
        Create sections if missing.
        Increment: total_input_tokens, total_output_tokens, total_requests
        """
        ...
    
    def _process_result(
        self,
        request: LLMRequest,
        result: AdapterResponse | BaseException,
    ) -> T | LLMError:
        """
        Convert gather result to return type.
        
        If AdapterResponse: return result.parsed
        If LLMError: return as-is
        If other Exception: wrap in LLMError
        """
        ...
```

### Step 2: Update src/utils/__init__.py

Export public API:

```python
from src.utils.llm import LLMClient, LLMRequest, ResponseChainManager
```

### Step 3: Create Unit Tests

File: `tests/unit/test_llm.py`

Use mock adapter. Test all scenarios from spec.

#### Mock Adapter Pattern

```python
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel

class SimpleResponse(BaseModel):
    answer: str

@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.execute = AsyncMock()
    adapter.delete_response = AsyncMock(return_value=True)
    return adapter

def make_adapter_response(response_id: str, answer: str) -> AdapterResponse:
    return AdapterResponse(
        response_id=response_id,
        parsed=SimpleResponse(answer=answer),
        usage=ResponseUsage(
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=0,
            cached_tokens=0,
            total_tokens=150,
        ),
        debug=ResponseDebug(
            model="test-model",
            created_at=1234567890,
            service_tier=None,
            reasoning_summary=None,
        ),
    )
```

#### Test Groups

**ResponseChainManager tests:**
- test_init_indexes_entities — entities accessible by ID
- test_init_skips_entities_without_id — no crash, just skip
- test_init_empty_list — works with []
- test_get_previous_empty_chain — returns None
- test_get_previous_with_chain — returns last ID
- test_get_previous_unknown_entity — returns None
- test_confirm_depth_zero — returns None, no mutation
- test_confirm_creates_openai_section — section created
- test_confirm_creates_chain — chain created
- test_confirm_appends_to_chain — ID added
- test_confirm_sliding_window_evicts — oldest removed when full
- test_confirm_unknown_entity — returns None
- test_parse_key_formats — all chain types work

**LLMClient initialization tests:**
- test_client_stores_adapter
- test_client_creates_chain_manager
- test_client_stores_default_depth
- test_client_empty_entities

**LLMClient.create_response tests:**
- test_create_response_success — returns parsed model
- test_create_response_uses_chain — get_previous called
- test_create_response_confirms — confirm called with default_depth
- test_create_response_accumulates_usage
- test_create_response_without_entity_key — no chain interaction
- test_create_response_propagates_refusal
- test_create_response_propagates_timeout

**LLMClient.create_batch tests:**
- test_batch_empty_list — returns []
- test_batch_all_success — all parsed models
- test_batch_preserves_order
- test_batch_partial_failure — mix of results and errors
- test_batch_all_failure
- test_batch_uses_previous_response_id
- test_batch_confirms_with_depth_override
- test_batch_confirms_with_default_depth
- test_batch_deletes_evicted
- test_batch_accumulates_usage_per_entity

**Usage accumulation tests:**
- test_accumulate_creates_openai_section
- test_accumulate_creates_usage_section
- test_accumulate_increments_counters
- test_accumulate_multiple_requests_sum

### Step 4: Create Integration Tests

File: `tests/integration/test_llm_integration.py`

These tests use REAL OpenAI API. They verify that chain management works correctly
with actual API behavior.

#### Setup

```python
"""Integration tests for LLMClient with real OpenAI API.

These tests require OPENAI_API_KEY environment variable.
They make real API calls and may incur costs.

Run with: pytest tests/integration/test_llm_integration.py -v
"""

import os
import pytest
from pydantic import BaseModel

from src.config import Config
from src.utils.llm import LLMClient, LLMRequest, ResponseChainManager
from src.utils.llm_adapters import OpenAIAdapter
from src.utils.llm_errors import LLMError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]


class SimpleAnswer(BaseModel):
    """Simple schema for tests."""
    answer: str


@pytest.fixture
def config():
    """Load config, skip if no API key."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    return Config.load()


@pytest.fixture
def make_entity():
    """Factory for test entities."""
    def _make(entity_id: str) -> dict:
        return {
            "identity": {"id": entity_id},
            "state": {},
        }
    return _make
```

#### Test: Sliding Window Eviction

This is the KEY test — verifies that when chain is full, old responses are deleted.

```python
class TestChainManagement:
    """Tests for response chain with real API."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_sliding_window_eviction(self, config, make_entity):
        """
        Test that sliding window evicts and deletes old responses.
        
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
        response_ids = []
        
        # Request 1
        result1 = await client.create_response(
            instructions="Remember information given to you.",
            input_data="The secret code is ALPHA.",
            schema=SimpleAnswer,
            entity_key="intention:test-char",
        )
        chain = entity["_openai"]["intention_chain"]
        assert len(chain) == 1
        response_ids.append(chain[0])
        
        # Request 2
        result2 = await client.create_response(
            instructions="Remember information given to you.",
            input_data="The second code is BETA.",
            schema=SimpleAnswer,
            entity_key="intention:test-char",
        )
        chain = entity["_openai"]["intention_chain"]
        assert len(chain) == 2
        response_ids.append(chain[1])
        
        # Request 3 — should evict request 1
        result3 = await client.create_response(
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
        # Try to use it as previous_response_id — should fail
        try:
            await adapter.client.responses.retrieve(response_ids[0])
            pytest.fail("Expected 404 for deleted response")
        except Exception as e:
            # Should get 404 or similar error
            assert "404" in str(e) or "not found" in str(e).lower()
        
        # Cleanup remaining responses
        for resp_id in chain:
            await adapter.delete_response(resp_id)
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_chain_context_preserved(self, config, make_entity):
        """
        Test that chain preserves context across requests.
        
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
            instructions="Recall the user's name from context.",
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
    async def test_independent_requests_no_context(self, config, make_entity):
        """
        Test that depth=0 means independent requests (no chain).
        
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
            instructions="What password was mentioned? Say 'none' if unknown.",
            input_data="Tell me the password.",
            schema=SimpleAnswer,
            entity_key="intention:no-chain-test",
        )
        
        # Should NOT know the password (no chain context)
        answer_lower = result.answer.lower()
        assert "secret123" not in answer_lower
        
        # Verify no chain was created
        assert "intention_chain" not in entity.get("_openai", {})
```

#### Test: Batch with Chains

```python
class TestBatchWithChains:
    """Tests for batch execution with chains."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_batch_parallel_chain_updates(self, config, make_entity):
        """
        Test that parallel batch requests update chains correctly.
        
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
```

#### Test: Usage Accumulation

```python
class TestUsageAccumulation:
    """Tests for usage tracking."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_usage_persisted_in_entity(self, config, make_entity):
        """
        Test that usage stats are accumulated in entity.
        """
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
        assert usage["total_input_tokens"] > 0
        assert usage["total_output_tokens"] > 0
        
        # Cleanup
        for resp_id in entity.get("_openai", {}).get("intention_chain", []):
            await adapter.delete_response(resp_id)
```

#### Test: Edge Cases

```python
class TestEdgeCases:
    """Edge case tests."""
    
    @pytest.mark.asyncio
    async def test_empty_batch(self, config, make_entity):
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
    async def test_chain_survives_partial_failure(self, config, make_entity):
        """
        If one request fails, others still update chains.
        
        Note: This test is tricky to trigger reliably.
        We use a very short timeout for one request.
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
```

## Testing

### Run Unit Tests

```bash
cd /path/to/thing-sandbox
source venv/bin/activate

# Unit tests only (fast, no API)
pytest tests/unit/test_llm.py -v

# With coverage
pytest tests/unit/test_llm.py -v --cov=src/utils/llm --cov-report=term-missing
```

### Run Integration Tests

```bash
# Integration tests (requires OPENAI_API_KEY)
export OPENAI_API_KEY="sk-..."
pytest tests/integration/test_llm_integration.py -v -s

# All integration tests
pytest -m integration -v -s
```

### Run All Quality Checks

```bash
ruff check src/utils/llm.py tests/unit/test_llm.py tests/integration/test_llm_integration.py
ruff format src/utils/llm.py tests/unit/test_llm.py tests/integration/test_llm_integration.py
mypy src/utils/llm.py
pytest tests/unit/test_llm.py -v
```

## Deliverables

1. **src/utils/llm.py** — LLMClient, LLMRequest, ResponseChainManager
2. **src/utils/__init__.py** — updated exports
3. **tests/unit/test_llm.py** — comprehensive unit tests with mock adapter
4. **tests/integration/test_llm_integration.py** — integration tests with real API
5. **Report** — TS-A.5c-LLM-001_REPORT.md with:
   - Implementation summary
   - Test results (unit + integration)
   - Any deviations from spec
   - Coverage report

## Success Criteria

- [ ] All unit tests pass
- [ ] All integration tests pass (with API key - ask use for the key)
- [ ] ruff check passes
- [ ] ruff format passes  
- [ ] mypy passes
- [ ] Coverage > 90% for src/utils/llm.py
