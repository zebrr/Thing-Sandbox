# util_llm.md

## Status: DRAFT

Provider-agnostic LLM client facade. Handles batch execution, response chains, 
and usage accumulation. Phases work only with this interface.

---

## Public API

### LLMClient

Provider-agnostic facade for LLM requests. Created per-phase with corresponding 
adapter and entities.

```python
class LLMClient:
    def __init__(
        self,
        adapter: OpenAIAdapter,
        entities: list[dict],
        default_depth: int = 0,
    ) -> None
    
    async def create_response(
        self,
        instructions: str,
        input_data: str,
        schema: type[T],
        entity_key: str | None = None,
    ) -> T
    
    async def create_batch(
        self,
        requests: list[LLMRequest],
    ) -> list[T | LLMError]
```

#### LLMClient.\_\_init\_\_(adapter, entities, default_depth) -> None

Creates client instance for a specific phase.

- **Input**:
  - adapter — LLM provider adapter (OpenAIAdapter, etc.)
  - entities — list of characters or locations (mutated in-place)
  - default_depth — default chain depth from PhaseConfig (0 = independent requests)
- **Behavior**:
  - Creates ResponseChainManager with provided entities
  - Stores adapter and default_depth for later use

#### LLMClient.create_response(...) -> T

Single request to LLM with structured output.

- **Input**:
  - instructions (str) — system prompt
  - input_data (str) — user content (character context, location data, etc.)
  - schema (type[T]) — Pydantic model class for structured output
  - entity_key (str | None) — key for response chain ("intention:bob"), None for independent request
- **Returns**: Instance of schema with parsed response
- **Raises**:
  - `LLMRefusalError` — model refused due to safety
  - `LLMIncompleteError` — response truncated (max_output_tokens reached)
  - `LLMRateLimitError` — rate limit after all retries
  - `LLMTimeoutError` — timeout after all retries
  - `LLMError` — other API errors
- **Behavior**:
  1. Get previous_response_id from chain (if entity_key provided)
  2. Execute request via adapter
  3. Auto-confirm: add to chain with default_depth
  4. Accumulate usage in entity
  5. Return parsed response

#### LLMClient.create_batch(requests) -> list[T | LLMError]

Batch of parallel requests.

- **Input**:
  - requests — list of LLMRequest objects
- **Returns**: List of results in same order. Successful — schema instances. Failed — LLMError instances (not raised, returned in list).
- **Behavior**:
  1. Execute all requests in parallel via `asyncio.gather(..., return_exceptions=True)`
  2. For each request: get previous_id, execute, auto-confirm, accumulate usage
  3. Convert exceptions to LLMError instances in result list
  4. Log warning if rate limit hits occurred
- **Note**: Retry happens inside adapter for each request. LLMError in result means all attempts exhausted.

---

### LLMRequest

Request data for batch execution.

```python
@dataclass
class LLMRequest:
    instructions: str
    input_data: str
    schema: type[BaseModel]
    entity_key: str | None = None
    depth_override: int | None = None
```

- **instructions** — system prompt
- **input_data** — user content
- **schema** — Pydantic model class for structured output
- **entity_key** — key for response chain, None for independent request
- **depth_override** — override default chain depth for this specific request (None = use default)

---

### ResponseChainManager

Stateless helper for managing response chains in entities.

```python
class ResponseChainManager:
    def __init__(self, entities: list[dict]) -> None
    def get_previous(self, entity_key: str) -> str | None
    def confirm(self, entity_key: str, response_id: str, depth: int) -> str | None
```

#### ResponseChainManager.\_\_init\_\_(entities) -> None

Creates manager with entity index.

- **Input**:
  - entities — list of characters or locations (mutated in-place). Each must have `identity.id`.
- **Behavior**:
  - Builds internal dict mapping entity_id → entity for O(1) lookup

#### ResponseChainManager.get_previous(entity_key) -> str | None

Get last response_id from chain for entity.

- **Input**:
  - entity_key — key like "intention:bob", "memory:elvira"
- **Returns**: response_id or None if chain is empty
- **Behavior**:
  - Parse entity_key into (entity_id, chain_name)
  - Look up `entity["_openai"]["{chain_name}_chain"][-1]`

#### ResponseChainManager.confirm(entity_key, response_id, depth) -> str | None

Add response to chain (mutates entity in-place).

- **Input**:
  - entity_key — key like "intention:bob", "memory:elvira"
  - response_id — response ID from OpenAI
  - depth — chain depth (0 = don't add, >0 = sliding window)
- **Returns**: Evicted response_id (for deletion) or None
- **Behavior**:
  - If depth == 0: return None (independent requests)
  - Parse entity_key into (entity_id, chain_name)
  - Ensure `entity["_openai"]["{chain_name}_chain"]` exists
  - If chain length >= depth: pop oldest (evicted)
  - Append new response_id
  - Return evicted or None

---

## Entity Key Format

Entity keys follow pattern: `"{chain_type}:{entity_id}"`

| Chain Type | Used In | Example |
|------------|---------|---------|
| intention | Phase 1 | "intention:bob" |
| memory | Phase 4 | "memory:elvira" |
| resolution | Phase 2a | "resolution:tavern" |
| narrative | Phase 2b | "narrative:forest" |

This allows single entity to have different chains for different phases.

---

## Chain Storage in Entities

Chains stored in entity's `_openai` namespace:

```json
// characters/bob.json
{
  "identity": {"id": "bob", ...},
  "state": {...},
  "_openai": {
    "intention_chain": ["resp_abc123", "resp_def456"],
    "memory_chain": ["resp_xyz789"],
    "usage": {
      "total_input_tokens": 125000,
      "total_output_tokens": 8500,
      "total_requests": 42
    }
  }
}
```

```json
// locations/tavern.json
{
  "identity": {"id": "tavern", ...},
  "state": {...},
  "_openai": {
    "resolution_chain": ["resp_111", "resp_222"],
    "narrative_chain": ["resp_333"],
    "usage": {...}
  }
}
```

**Chain key naming**: `{chain_type}_chain` (e.g., "intention_chain", "memory_chain")

---

## Internal Design

### Batch Execution Flow

```python
async def create_batch(self, requests: list[LLMRequest]) -> list[T | LLMError]:
    # Parallel execution with exception capture
    tasks = [self._execute_one(r) for r in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert to uniform result list
    return [self._process_result(r, res) for r, res in zip(requests, results)]

async def _execute_one(self, request: LLMRequest) -> AdapterResponse:
    # 1. Get previous_response_id from chain
    previous_id = None
    if request.entity_key:
        previous_id = self.chain_manager.get_previous(request.entity_key)
    
    # 2. Execute via adapter (retry inside)
    response = await self.adapter.execute(
        instructions=request.instructions,
        input_data=request.input_data,
        schema=request.schema,
        previous_response_id=previous_id,
    )
    
    # 3. Auto-confirm with appropriate depth
    if request.entity_key:
        depth = request.depth_override if request.depth_override is not None else self.default_depth
        evicted = self.chain_manager.confirm(request.entity_key, response.response_id, depth)
        if evicted:
            await self.adapter.delete_response(evicted)
    
    # 4. Accumulate usage
    if request.entity_key:
        self._accumulate_usage(request.entity_key, response.usage)
    
    return response

def _process_result(self, request: LLMRequest, result: AdapterResponse | BaseException) -> T | LLMError:
    if isinstance(result, BaseException):
        if isinstance(result, LLMError):
            return result
        return LLMError(f"Unexpected error: {result}")
    return result.parsed
```

### Usage Accumulation

```python
def _accumulate_usage(self, entity_key: str, usage: ResponseUsage) -> None:
    entity_id, _ = self.chain_manager._parse_key(entity_key)
    entity = self.chain_manager.entities.get(entity_id)
    if not entity:
        return
    
    if "_openai" not in entity:
        entity["_openai"] = {}
    
    if "usage" not in entity["_openai"]:
        entity["_openai"]["usage"] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_requests": 0,
        }
    
    stats = entity["_openai"]["usage"]
    stats["total_input_tokens"] += usage.input_tokens
    stats["total_output_tokens"] += usage.output_tokens
    stats["total_requests"] += 1
```

### Entity Key Parsing

```python
def _parse_key(self, entity_key: str) -> tuple[str, str]:
    """
    Parse entity_key into (entity_id, chain_name).
    
    "intention:bob" → ("bob", "intention")
    "memory:elvira" → ("elvira", "memory")
    """
    chain_name, entity_id = entity_key.split(":", 1)
    return entity_id, chain_name
```

---

## File Structure

```
src/utils/
├── llm.py                    # LLMClient, LLMRequest, ResponseChainManager
├── llm_errors.py             # LLMError hierarchy (existing)
└── llm_adapters/
    ├── __init__.py           # Public exports (existing)
    ├── base.py               # AdapterResponse, ResponseUsage (existing)
    └── openai.py             # OpenAIAdapter (existing)
```

### llm.py

```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from src.utils.llm_adapters.base import AdapterResponse, ResponseUsage
from src.utils.llm_errors import LLMError

if TYPE_CHECKING:
    from src.utils.llm_adapters.openai import OpenAIAdapter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMRequest:
    ...


class ResponseChainManager:
    ...


class LLMClient:
    ...
```

---

## Dependencies

- **Standard Library**: asyncio, logging, dataclasses, typing
- **External**: pydantic>=2.0
- **Internal**:
  - src.utils.llm_errors (LLMError and subclasses)
  - src.utils.llm_adapters.base (AdapterResponse, ResponseUsage)
  - src.utils.llm_adapters.openai (OpenAIAdapter) — TYPE_CHECKING only

---

## Usage Examples

### Phase 1: Character Intentions

```python
from pydantic import BaseModel
from src.config import Config
from src.utils.llm import LLMClient, LLMRequest
from src.utils.llm_adapters.openai import OpenAIAdapter
from src.utils.llm_errors import LLMError


class IntentionResponse(BaseModel):
    intention: str
    target: str | None = None
    reasoning: str


async def process_intentions(
    characters: list[dict],
    config: Config,
) -> list[IntentionResponse]:
    # Create client for Phase 1
    adapter = OpenAIAdapter(config.phase1)
    client = LLMClient(
        adapter=adapter,
        entities=characters,
        default_depth=config.phase1.response_chain_depth,
    )
    
    # Build requests
    prompt = load_prompt("phase1_intention")
    requests = [
        LLMRequest(
            instructions=prompt,
            input_data=build_character_context(char),
            schema=IntentionResponse,
            entity_key=f"intention:{char['identity']['id']}",
        )
        for char in characters
    ]
    
    # Execute batch
    results = await client.create_batch(requests)
    
    # Handle results with fallback
    intentions = []
    for char, result in zip(characters, results):
        if isinstance(result, LLMError):
            logger.warning(f"Phase 1 failed for {char['identity']['id']}: {result}")
            intentions.append(IntentionResponse(
                intention="idle",
                target=None,
                reasoning="LLM error, using fallback",
            ))
        else:
            intentions.append(result)
    
    return intentions
```

### Phase 2a: Location Resolution (with chain depth)

```python
class MasterResponse(BaseModel):
    outcomes: list[dict]
    location_update: dict | None = None


async def process_resolutions(
    locations: list[dict],
    intentions: dict[str, list],  # location_id → intentions
    config: Config,
) -> list[MasterResponse]:
    adapter = OpenAIAdapter(config.phase2a)
    client = LLMClient(
        adapter=adapter,
        entities=locations,
        default_depth=config.phase2a.response_chain_depth,  # e.g., 2
    )
    
    prompt = load_prompt("phase2_master")
    requests = [
        LLMRequest(
            instructions=prompt,
            input_data=build_location_context(loc, intentions[loc["identity"]["id"]]),
            schema=MasterResponse,
            entity_key=f"resolution:{loc['identity']['id']}",
        )
        for loc in locations
    ]
    
    results = await client.create_batch(requests)
    
    # Handle with fallback...
    return [
        r if not isinstance(r, LLMError) else MasterResponse.empty_fallback()
        for r in results
    ]
```

### Single Request (without batch)

```python
async def summarize_memory(
    character: dict,
    old_summary: str,
    evicted_cell: str,
    config: Config,
) -> str:
    adapter = OpenAIAdapter(config.phase4)
    client = LLMClient(
        adapter=adapter,
        entities=[character],
        default_depth=config.phase4.response_chain_depth,
    )
    
    prompt = load_prompt("phase4_summary")
    
    result = await client.create_response(
        instructions=prompt,
        input_data=f"Summary: {old_summary}\n\nEvicted: {evicted_cell}",
        schema=SummaryResponse,
        entity_key=f"memory:{character['identity']['id']}",
    )
    
    return result.new_summary
```

### Different Depth per Entity (future use)

```python
# Special character with longer memory chain
requests = [
    LLMRequest(
        instructions=prompt,
        input_data=context,
        schema=IntentionResponse,
        entity_key="intention:bob",
        depth_override=5,  # Bob has longer context
    ),
    LLMRequest(
        instructions=prompt,
        input_data=context,
        schema=IntentionResponse,
        entity_key="intention:alice",
        # Uses default_depth from client
    ),
]
```

---

## Test Coverage

### Unit Tests (mock adapter)

File: `tests/unit/test_llm.py`

**LLMClient Initialization:**
- test_client_init_creates_chain_manager — entities indexed correctly
- test_client_init_stores_default_depth — default_depth accessible
- test_client_init_empty_entities — works with empty list

**Single Request (create_response):**
- test_create_response_success — returns parsed schema instance
- test_create_response_with_entity_key — uses chain, accumulates usage
- test_create_response_without_entity_key — no chain interaction
- test_create_response_propagates_errors — LLMError raised

**Batch Execution (create_batch):**
- test_batch_all_success — all results are schema instances
- test_batch_partial_failure — mix of results and LLMError
- test_batch_all_failure — all LLMError
- test_batch_empty_requests — returns empty list
- test_batch_preserves_order — results match request order

**Chain Integration:**
- test_batch_uses_previous_response_id — get_previous called
- test_batch_auto_confirm — confirm called with correct depth
- test_batch_depth_override — request depth_override used
- test_batch_eviction_triggers_delete — delete_response called

**Usage Accumulation:**
- test_usage_accumulated_per_entity — stats updated correctly
- test_usage_creates_openai_section — section created if missing
- test_usage_multiple_requests — stats sum correctly

**ResponseChainManager:**
- test_chain_manager_init_indexes_entities — entities by id
- test_chain_manager_init_skips_invalid — entities without id skipped
- test_get_previous_empty_chain — returns None
- test_get_previous_with_chain — returns last id
- test_get_previous_unknown_entity — returns None
- test_confirm_depth_zero — returns None, no mutation
- test_confirm_adds_to_chain — chain updated
- test_confirm_sliding_window — oldest evicted when full
- test_confirm_creates_openai_section — section created if missing
- test_confirm_unknown_entity — returns None
- test_parse_key_intention — correct parsing
- test_parse_key_memory — correct parsing
- test_parse_key_resolution — correct parsing

**LLMRequest:**
- test_request_defaults — entity_key and depth_override are None
- test_request_with_override — depth_override set

### Integration Tests (real API)

File: `tests/integration/test_llm_integration.py`

Markers: `@pytest.mark.integration`, `@pytest.mark.slow`

Skip condition: `OPENAI_API_KEY` not set

**Chain Management:**
- test_sliding_window_eviction — depth=2, make 3 requests, verify first response deleted from OpenAI (retrieve → 404)
- test_chain_context_preserved — save name in request 1, ask in request 2, should remember
- test_deleted_response_not_usable — delete response, try as previous_response_id → LLMError
- test_independent_requests_no_context — depth=0, requests don't share context

**Batch with Chains:**
- test_batch_parallel_chain_updates — parallel requests for different entities update their chains correctly
- test_batch_same_entity_sequential — multiple requests for same entity processed correctly (last wins)

**Usage Accumulation:**
- test_usage_persisted_in_entity — after requests, entity["_openai"]["usage"] contains correct totals

**Edge Cases:**
- test_chain_survives_partial_failure — one request fails, others still update chains
- test_empty_batch — empty request list returns empty result

---

## Error Handling

### In create_response

Exceptions propagate to caller. Phase decides on fallback.

```python
try:
    result = await client.create_response(...)
except LLMRefusalError as e:
    logger.warning(f"Model refused: {e.refusal_message}")
    return fallback_response()
except LLMIncompleteError as e:
    logger.error(f"Response truncated: {e.reason}")
    raise  # Or use fallback
except LLMError as e:
    logger.error(f"LLM error: {e}")
    return fallback_response()
```

### In create_batch

Exceptions captured, returned as LLMError in result list.

```python
results = await client.create_batch(requests)

for request, result in zip(requests, results):
    if isinstance(result, LLMError):
        logger.warning(f"Request failed: {result}")
        # Use fallback for this entity
    else:
        # Process successful result
```

---

## Configuration Integration

LLMClient receives depth from PhaseConfig:

```python
# In phase module
client = LLMClient(
    adapter=OpenAIAdapter(config.phase1),
    entities=characters,
    default_depth=config.phase1.response_chain_depth,
)
```

Each phase can have different depth:

```toml
# config.toml
[phase1]
response_chain_depth = 0    # Independent requests

[phase2a]
response_chain_depth = 2    # Sliding window of 2

[phase2b]
response_chain_depth = 0

[phase4]
response_chain_depth = 0
```

---

## Design Decisions

### Why depth in confirm(), not in constructor?

Allows flexibility:
1. Different phases have different depths (via default_depth)
2. Different entities can have different depths (via depth_override)
3. Future: per-entity persistent depth config

### Why auto-confirm?

Structured Outputs guarantee valid response. If response parsed successfully, 
it's valid — no need for two-phase confirmation like in k2-18.

### Why return LLMError in batch instead of raising?

Partial failures shouldn't abort entire batch. Phase can apply fallback 
per-entity and continue simulation.

### Why mutate entities in-place?

Simplifies data flow:
1. Runner loads entities via Storage
2. Phases use LLMClient, chains/usage mutated
3. Runner saves entities via Storage
4. No need to return updated entities from phases

---

## Implementation Notes

### Logging

- DEBUG: request started, response received, chain operations
- WARNING: rate limit retries (from adapter), fallbacks used
- ERROR: before raising exceptions

```python
logger.debug(f"Executing request for {entity_key}")
logger.debug(f"Chain get_previous({entity_key}) = {previous_id}")
logger.debug(f"Chain confirm({entity_key}, {response_id}, depth={depth}) = evicted:{evicted}")
logger.warning(f"Batch had {rate_limit_hits} rate limit hits")
```

### Thread Safety

Not thread-safe. Designed for single-threaded async execution within one tick.
Each tick processes sequentially: Phase 1 → 2a → 2b → 3 → 4.

### Memory Considerations

ChainManager holds references to entity dicts, not copies. 
Mutations visible immediately. No deep copying overhead.
