# util_llm_adapter_openai.md

## Status: READY

OpenAI Responses API adapter. Executes requests with retry logic, timeout handling, 
and structured output parsing via Pydantic models.

---

## Public API

### OpenAIAdapter

Adapter for OpenAI Responses API. Stateless — create per-request with phase configuration.

```python
class OpenAIAdapter:
    def __init__(self, config: PhaseConfig) -> None
    async def execute(
        self,
        instructions: str,
        input_data: str,
        schema: type[T],
        previous_response_id: str | None = None,
    ) -> AdapterResponse[T]
    async def delete_response(self, response_id: str) -> bool
```

#### OpenAIAdapter.\_\_init\_\_(config: PhaseConfig) -> None

Creates adapter instance with phase configuration.

- **Input**:
  - config — phase configuration (model, timeout, retry settings, etc.)
- **Behavior**:
  - Creates `AsyncOpenAI` client with configured timeout
  - Reads `OPENAI_API_KEY` from environment
- **Raises**:
  - `LLMError` — if `OPENAI_API_KEY` not set

#### OpenAIAdapter.execute(...) -> AdapterResponse[T]

Executes single request to OpenAI API with structured output.

- **Input**:
  - instructions (str) — system prompt
  - input_data (str) — user content (character context, location data, etc.)
  - schema (type[T]) — Pydantic model class for structured output
  - previous_response_id (str | None) — for response chain continuity, default None
- **Returns**: `AdapterResponse[T]` with parsed response, usage stats, and response_id
- **Raises**:
  - `LLMRefusalError` — model refused due to safety
  - `LLMIncompleteError` — response truncated (max_output_tokens reached)
  - `LLMRateLimitError` — rate limit after all retries exhausted
  - `LLMTimeoutError` — timeout after all retries exhausted
  - `LLMError` — other API errors (invalid model, broken chain, etc.)
- **Behavior**:
  1. Build request with configured parameters
  2. Call `client.responses.parse()` with Pydantic schema
  3. On rate limit (429) — wait per header, retry up to `max_retries`
  4. On timeout — retry up to `max_retries`
  5. On success — extract parsed object, usage, response_id
  6. On refusal/incomplete — raise immediately (no retry)
- **Note**: Retry happens silently inside. Caller sees only final result or error.

#### OpenAIAdapter.delete_response(response_id: str) -> bool

Deletes response from OpenAI storage (for chain cleanup).

- **Input**:
  - response_id — ID of response to delete
- **Returns**: True if deleted, False if error
- **Behavior**:
  - Calls `DELETE /v1/responses/{response_id}`
  - On error — logs warning, returns False (never raises)
- **Note**: Deletion errors are non-critical. Logging is sufficient.

---

## Configuration Dependency

Adapter receives `PhaseConfig` from `src/config.py`. Required fields:

| Field | Type | Used For |
|-------|------|----------|
| model | str | Model identifier (e.g., "gpt-5-mini-2025-08-07") |
| timeout | int | httpx timeout in seconds |
| max_retries | int | Retry attempts for rate limit/timeout |
| max_completion | int | Maps to API's max_output_tokens parameter |
| is_reasoning | bool | Enables reasoning parameters |
| reasoning_effort | str \| None | "minimal", "low", "medium", "high" |
| reasoning_summary | str \| None | "auto", "concise", "detailed" |
| truncation | str \| None | "auto" or "disabled" |
| verbosity | str \| None | "low", "medium", "high" (GPT-5 only) |

See `docs/specs/core_config.md` for full PhaseConfig specification.

---

## Internal Design

### Request Building

```python
response = await self.client.responses.parse(
    model=config.model,
    instructions=instructions,
    input=input_data,
    text_format=schema,
    max_output_tokens=config.max_completion,  # PhaseConfig.max_completion → API max_output_tokens
    previous_response_id=previous_response_id,
    store=True,
    # Conditional parameters:
    reasoning={"effort": ..., "summary": ...},  # if is_reasoning
    truncation=config.truncation,                # if set
    verbosity=config.verbosity,                  # if set (GPT-5 only)
)
```

### Retry Logic

```python
for attempt in range(max_retries + 1):
    try:
        response = await _do_request(...)
        return _process_response(response)
    except RateLimitError as e:
        if attempt >= max_retries:
            raise LLMRateLimitError(f"Rate limit after {attempt + 1} attempts")
        wait = _parse_reset_ms(e.response.headers)
        logger.warning(f"Rate limit, waiting {wait}s (attempt {attempt + 1})")
        await asyncio.sleep(wait)
    except httpx.TimeoutException:
        if attempt >= max_retries:
            raise LLMTimeoutError(f"Timeout after {attempt + 1} attempts")
        logger.warning(f"Timeout, retrying (attempt {attempt + 1})")
        await asyncio.sleep(1.0)
```

**Retry policy:**
- Rate limit (429): wait per `x-ratelimit-reset-tokens` header + 0.5s buffer
- Timeout: fixed 1 second delay
- Refusal: no retry, raise immediately
- Incomplete: no retry, raise immediately

### Response Processing

```python
def _process_response(self, response) -> AdapterResponse[T]:
    # Check status
    if response.status == "incomplete":
        raise LLMIncompleteError(response.incomplete_details.reason)
    if response.status == "failed":
        raise LLMError(f"Request failed: {response.error.message}")

    # Check for refusal (response.output[0].content[0] contains refusal info)
    # Note: With responses.parse(), output_parsed will be None on refusal
    content = response.output[0].content[0]
    if content.type == "refusal":
        raise LLMRefusalError(content.refusal)  # content.refusal is a string

    # Extract usage (including cached_tokens and total_tokens)
    usage = ResponseUsage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        reasoning_tokens=response.usage.output_tokens_details.reasoning_tokens or 0,
        cached_tokens=response.usage.input_tokens_details.cached_tokens or 0,
        total_tokens=response.usage.total_tokens,
    )

    # Extract debug info
    reasoning_summary = None
    for item in response.output:
        if item.type == "reasoning":
            reasoning_summary = [s.text for s in item.summary if s.type == "summary_text"]
            break

    debug = ResponseDebugInfo(
        model=response.model,
        created_at=response.created_at,
        service_tier=response.service_tier,
        reasoning_summary=reasoning_summary,
    )

    # Return parsed response (SDK already parsed via text_format)
    # output_parsed contains Pydantic model instance
    return AdapterResponse(
        response_id=response.id,
        parsed=response.output_parsed,
        usage=usage,
        debug=debug,
    )
```

### Output Unification

SDK's `parse()` with `text_format` parameter handles:
- Regular models: extracts from `output[0].content[0]`
- Reasoning models: extracts from `output[1].content[0]`

Adapter receives already-parsed Pydantic object in `response.output_parsed`.

### Rate Limit Header Parsing

```python
def _parse_reset_ms(self, headers: httpx.Headers) -> float:
    """Parse reset time from headers, return seconds."""
    reset_str = headers.get("x-ratelimit-reset-tokens", "1000ms")
    ms = int(reset_str.rstrip("ms"))
    return ms / 1000 + 0.5  # Add 0.5s buffer
```

---

## File Structure

```
src/utils/llm_adapters/
├── __init__.py
├── base.py                   # AdapterResponse, ResponseDebugInfo, ResponseUsage
└── openai.py                 # OpenAIAdapter (this module)
```

### openai.py

```python
import asyncio
import logging
import os

import httpx
from openai import AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from src.config import PhaseConfig
from src.utils.llm_errors import (
    LLMError,
    LLMIncompleteError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)
from src.utils.llm_adapters.base import AdapterResponse, ResponseDebugInfo, ResponseUsage

logger = logging.getLogger(__name__)

class OpenAIAdapter:
    ...
```

---

## Dependencies

- **Standard Library**: asyncio, os, logging
- **External**: openai>=1.0.0, httpx, pydantic>=2.0
- **Internal**: 
  - src.config.PhaseConfig
  - src.utils.llm_errors (LLMError, LLMRefusalError, etc.)
  - src.utils.llm_adapters.base (AdapterResponse, ResponseUsage)

---

## Usage Examples

### Basic Request

```python
from pydantic import BaseModel
from src.config import Config
from src.utils.llm_adapters import OpenAIAdapter

class SimpleResponse(BaseModel):
    answer: str
    confidence: float

config = Config.load()
adapter = OpenAIAdapter(config.phase1)

response = await adapter.execute(
    instructions="Answer briefly with confidence score.",
    input_data="What is 2+2?",
    schema=SimpleResponse,
)

print(response.parsed.answer)       # "4"
print(response.parsed.confidence)   # 0.99
print(response.usage.input_tokens)  # 25
```

### With Response Chain

```python
# First request
response1 = await adapter.execute(
    instructions="Remember the user's name.",
    input_data="My name is Alice.",
    schema=AckResponse,
)

# Second request with chain
response2 = await adapter.execute(
    instructions="Recall the name.",
    input_data="What was my name?",
    schema=NameResponse,
    previous_response_id=response1.response_id,
)

print(response2.parsed.name)  # "Alice"

# Cleanup
await adapter.delete_response(response1.response_id)
```

### Error Handling

```python
from src.utils.llm_errors import (
    LLMError,
    LLMRefusalError,
    LLMIncompleteError,
    LLMRateLimitError,
    LLMTimeoutError,
)

try:
    response = await adapter.execute(...)
except LLMRefusalError as e:
    logger.warning(f"Model refused: {e.refusal_message}")
    return fallback_response()
except LLMIncompleteError as e:
    logger.error(f"Response truncated: {e.reason}")
    raise
except LLMRateLimitError:
    logger.error("Rate limit exhausted")
    raise
except LLMTimeoutError:
    logger.error("Request timeout")
    raise
except LLMError as e:
    logger.error(f"LLM error: {e}")
    raise
```

---

## Test Coverage

### Unit Tests (mock AsyncOpenAI)

File: `tests/unit/test_llm_adapter_openai.py`

**Retry Logic:**
- test_retry_on_rate_limit — 429 → wait → retry → success
- test_retry_exhausted_rate_limit — 429 × (max_retries+1) → LLMRateLimitError
- test_retry_on_timeout — timeout → retry → success
- test_retry_exhausted_timeout — timeout × (max_retries+1) → LLMTimeoutError
- test_no_retry_on_refusal — refusal → immediate LLMRefusalError
- test_no_retry_on_incomplete — incomplete → immediate LLMIncompleteError

**Response Parsing:**
- test_parse_successful_response — completed → AdapterResponse with parsed
- test_parse_refusal_content — refusal type → LLMRefusalError

**Status Handling:**
- test_status_completed — status=completed → success
- test_status_failed — status=failed → LLMError with message
- test_status_incomplete — status=incomplete → LLMIncompleteError with reason

**Usage Extraction:**
- test_usage_regular_model — input_tokens, output_tokens extracted
- test_usage_reasoning_model — reasoning_tokens extracted from details

**Delete Response:**
- test_delete_success — returns True
- test_delete_not_found — returns False, logs warning
- test_delete_network_error — returns False, logs warning

### Integration Tests (real API)

File: `tests/integration/test_llm_adapter_openai_live.py`

Markers: `@pytest.mark.integration`, `@pytest.mark.slow`

Skip condition: `OPENAI_API_KEY` not set

**Happy Path:**
- test_simple_request — basic request → parsed Pydantic, response_id, usage
- test_structured_output — response matches schema
- test_reasoning_model — reasoning model works, reasoning_tokens > 0
- test_previous_response_id — chain context preserved
- test_chain_context_preserved — three requests, third remembers first
- test_delete_response — delete returns True

**Error Cases:**
- test_refusal — forbidden content → LLMRefusalError
- test_incomplete_response — max_output_tokens=30 → LLMIncompleteError
- test_invalid_api_key — bad key → LLMError

**Edge Cases:**
- test_deleted_response_as_previous — deleted response_id as previous → LLMError
- test_truncation_auto — truncation="auto" handles large context

---

## Implementation Notes

### AsyncOpenAI Client Setup

```python
import httpx
from openai import AsyncOpenAI

timeout = httpx.Timeout(config.timeout, connect=10.0)
self.client = AsyncOpenAI(timeout=timeout)
```

API key read from `OPENAI_API_KEY` environment variable automatically by SDK.

### Reasoning Parameters

Only passed when `config.is_reasoning` is True:

```python
if config.is_reasoning:
    params["reasoning"] = {}
    if config.reasoning_effort:
        params["reasoning"]["effort"] = config.reasoning_effort
    if config.reasoning_summary:
        params["reasoning"]["summary"] = config.reasoning_summary
```

### Logging

- DEBUG: request started, response received
- WARNING: retry attempt, delete failed
- ERROR: before raising exceptions

```python
logger.debug(f"Executing request to {config.model}")
logger.warning(f"Rate limit hit, waiting {wait}s (attempt {attempt + 1}/{max_retries + 1})")
logger.warning(f"Failed to delete response {response_id}: {e}")
logger.error(f"Request failed after {max_retries + 1} attempts: {e}")
```
