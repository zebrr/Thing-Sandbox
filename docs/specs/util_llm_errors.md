# util_llm_errors.md

## Status: IN_PROGRESS

Common types and exceptions for LLM adapters. Defines unified error hierarchy and 
response data types used by all adapter implementations.

---

## Public API

### Data Types

#### AdapterResponse[T]

Container for successful API response. Generic over Pydantic model type.

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass
class AdapterResponse(Generic[T]):
    response_id: str
    parsed: T
    usage: ResponseUsage
```

- **response_id** — provider's response ID (for chains, deletion, debugging)
- **parsed** — parsed response as Pydantic model instance
- **usage** — token usage statistics

#### ResponseUsage

Token usage statistics from API response.

```python
@dataclass
class ResponseUsage:
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0
```

- **input_tokens** — tokens in prompt
- **output_tokens** — tokens in response (excluding reasoning)
- **reasoning_tokens** — reasoning tokens (for reasoning models, 0 otherwise)

---

### Exceptions

All LLM-related exceptions inherit from `LLMError` base class.

#### LLMError

Base class for all LLM-related errors.

```python
class LLMError(Exception):
    """Base class for LLM-related errors."""
    pass
```

#### LLMRefusalError

Model refused request due to safety policy.

```python
class LLMRefusalError(LLMError):
    """Model refused request due to safety policy."""
    
    def __init__(self, refusal_message: str):
        self.refusal_message = refusal_message
        super().__init__(f"Model refused: {refusal_message}")
```

- **refusal_message** — explanation from model

#### LLMIncompleteError

Response truncated due to token limit.

```python
class LLMIncompleteError(LLMError):
    """Response truncated due to token limit."""
    
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Response incomplete: {reason}")
```

- **reason** — truncation reason from API (e.g., "max_output_tokens")

#### LLMRateLimitError

Rate limit exceeded after all retries.

```python
class LLMRateLimitError(LLMError):
    """Rate limit exceeded after all retries."""
    
    def __init__(self, message: str):
        super().__init__(message)
```

#### LLMTimeoutError

Request timeout after all retries.

```python
class LLMTimeoutError(LLMError):
    """Request timeout after all retries."""
    
    def __init__(self, message: str):
        super().__init__(message)
```

---

## Exit Code Mapping

For CLI/Runner error handling:

| Exception | Exit Code | When |
|-----------|-----------|------|
| LLMRefusalError | EXIT_RUNTIME_ERROR (3) | Safety refusal |
| LLMIncompleteError | EXIT_RUNTIME_ERROR (3) | Response truncated |
| LLMRateLimitError | EXIT_API_LIMIT_ERROR (4) | Rate limit exhausted |
| LLMTimeoutError | EXIT_RUNTIME_ERROR (3) | Timeout exhausted |
| LLMError | EXIT_RUNTIME_ERROR (3) | Other API errors |

---

## File Structure

```
src/utils/
├── llm_errors.py                 # This module
└── llm_adapters/
    ├── __init__.py
    ├── base.py                   # AdapterResponse, ResponseUsage
    └── openai.py                 # OpenAIAdapter (see util_llm_adapter_openai.md)
```

### llm_errors.py

Contains exception hierarchy only:

```python
class LLMError(Exception): ...
class LLMRefusalError(LLMError): ...
class LLMIncompleteError(LLMError): ...
class LLMRateLimitError(LLMError): ...
class LLMTimeoutError(LLMError): ...
```

### llm_adapters/base.py

Contains data types:

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass
class ResponseUsage:
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0

@dataclass
class AdapterResponse(Generic[T]):
    response_id: str
    parsed: T
    usage: ResponseUsage
```

---

## Dependencies

- **Standard Library**: dataclasses, typing
- **External**: None
- **Internal**: None

---

## Usage Examples

### Error Handling

```python
from src.utils.llm_errors import (
    LLMError,
    LLMRefusalError,
    LLMIncompleteError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.utils.exit_codes import (
    EXIT_RUNTIME_ERROR,
    EXIT_API_LIMIT_ERROR,
)

try:
    response = await adapter.execute(...)
except LLMRefusalError as e:
    logger.warning(f"Model refused: {e.refusal_message}")
    return fallback_response()
except LLMIncompleteError as e:
    logger.error(f"Response truncated: {e.reason}")
    sys.exit(EXIT_RUNTIME_ERROR)
except LLMRateLimitError:
    logger.error("Rate limit exhausted")
    sys.exit(EXIT_API_LIMIT_ERROR)
except LLMTimeoutError:
    logger.error("Request timeout")
    sys.exit(EXIT_RUNTIME_ERROR)
except LLMError as e:
    logger.error(f"LLM error: {e}")
    sys.exit(EXIT_RUNTIME_ERROR)
```

### Working with AdapterResponse

```python
from src.utils.llm_adapters.base import AdapterResponse, ResponseUsage

# Response from adapter
response: AdapterResponse[MySchema] = await adapter.execute(...)

# Access parsed data
print(response.parsed.field_name)

# Access usage stats
print(f"Input: {response.usage.input_tokens}")
print(f"Output: {response.usage.output_tokens}")
print(f"Reasoning: {response.usage.reasoning_tokens}")

# Store response_id for chain
chain.append(response.response_id)
```

---

## Test Coverage

### Unit Tests

File: `tests/unit/test_llm_errors.py`

- test_llm_error_base — base exception works
- test_llm_refusal_error_message — stores refusal_message
- test_llm_incomplete_error_reason — stores reason
- test_llm_rate_limit_error — message preserved
- test_llm_timeout_error — message preserved
- test_exception_hierarchy — all inherit from LLMError
- test_response_usage_defaults — reasoning_tokens defaults to 0
- test_adapter_response_generic — works with different Pydantic types
