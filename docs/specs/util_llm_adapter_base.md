# util_llm_adapter_base.md

## Status: READY

Base data types for LLM adapters. Defines common response types used by all
adapter implementations, providing a unified interface for adapter responses.

---

## Public API

### ResponseUsage

Dataclass for token usage statistics from API response.

```python
@dataclass
class ResponseUsage:
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
```

**Attributes:**
- **input_tokens** (int) — tokens in the request (prompt)
- **output_tokens** (int) — tokens in the response (completion)
- **reasoning_tokens** (int) — tokens used for reasoning (o1 models), default 0
- **cached_tokens** (int) — tokens served from cache, default 0
- **total_tokens** (int) — total tokens billed, default 0

**Note:** Not all fields populated by every provider. OpenAI populates all;
other adapters may leave defaults.

### ResponseDebugInfo

Dataclass for debug information extracted from API response.

```python
@dataclass
class ResponseDebugInfo:
    model: str
    created_at: int
    service_tier: str | None = None
    reasoning_summary: list[str] | None = None
```

**Attributes:**
- **model** (str) — actual model used (may differ from requested)
- **created_at** (int) — Unix timestamp of response creation
- **service_tier** (str | None) — OpenAI service tier, default None
- **reasoning_summary** (list[str] | None) — reasoning chain summary (o1 models), default None

**Note:** Always populated — parsing is cheap, transport layer decides what to log.

### AdapterResponse[T]

Generic dataclass for successful API response. Type parameter T must be
a Pydantic BaseModel subclass.

```python
T = TypeVar("T", bound=BaseModel)

@dataclass
class AdapterResponse(Generic[T]):
    response_id: str
    parsed: T
    usage: ResponseUsage
    debug: ResponseDebugInfo
```

**Type Parameter:**
- **T** — Pydantic model class for structured output (e.g., IntentionResponse)

**Attributes:**
- **response_id** (str) — unique identifier for response chaining
- **parsed** (T) — parsed and validated response object
- **usage** (ResponseUsage) — token consumption statistics
- **debug** (ResponseDebugInfo) — model and timing information

---

## Design Decisions

### Why Generic[T]?

- Type safety for parsed responses
- IDE autocompletion for response fields
- Clear contract between adapter and caller

### Why dataclass (not Pydantic)?

- These are internal transport containers
- No JSON serialization needed
- Minimal overhead for frequent instantiation

### Why separate ResponseUsage and ResponseDebugInfo?

- Clear separation of concerns
- Usage for billing/monitoring
- Debug for logging/troubleshooting
- Easy to extend independently

---

## Dependencies

- **Standard Library**: dataclasses, typing
- **External**: pydantic (BaseModel for type constraint)
- **Internal**: None

---

## Test Coverage

- **test_llm_adapter_base.py**: 8 tests
  - test_response_usage_defaults
  - test_response_usage_all_fields
  - test_response_debug_info_required_fields
  - test_response_debug_info_optional_fields
  - test_adapter_response_with_pydantic_model
  - test_adapter_response_generic_type
  - test_adapter_response_access_parsed_fields
  - test_response_usage_equality

---

## Usage Examples

### Creating ResponseUsage

```python
from src.utils.llm_adapters.base import ResponseUsage

# Minimal usage
usage = ResponseUsage(input_tokens=100, output_tokens=50)

# Full usage (OpenAI with reasoning)
usage = ResponseUsage(
    input_tokens=1000,
    output_tokens=200,
    reasoning_tokens=150,
    cached_tokens=500,
    total_tokens=1200,
)
```

### Creating ResponseDebugInfo

```python
from src.utils.llm_adapters.base import ResponseDebugInfo

debug = ResponseDebugInfo(
    model="gpt-4o-2024-08-06",
    created_at=1700000000,
    service_tier="default",
)
```

### Creating AdapterResponse

```python
from pydantic import BaseModel
from src.utils.llm_adapters.base import (
    AdapterResponse,
    ResponseDebugInfo,
    ResponseUsage,
)

class IntentionResponse(BaseModel):
    intention: str

usage = ResponseUsage(input_tokens=100, output_tokens=50)
debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)

response: AdapterResponse[IntentionResponse] = AdapterResponse(
    response_id="resp_abc123",
    parsed=IntentionResponse(intention="go to tavern"),
    usage=usage,
    debug=debug,
)

# Access parsed fields with type safety
print(response.parsed.intention)  # "go to tavern"
```

### In Adapter Implementation

```python
class OpenAIAdapter:
    async def call(self, ...) -> AdapterResponse[T]:
        api_response = await self._client.responses.create(...)

        usage = ResponseUsage(
            input_tokens=api_response.usage.input_tokens,
            output_tokens=api_response.usage.output_tokens,
        )

        debug = ResponseDebugInfo(
            model=api_response.model,
            created_at=api_response.created_at,
        )

        return AdapterResponse(
            response_id=api_response.id,
            parsed=parsed_output,
            usage=usage,
            debug=debug,
        )
```
