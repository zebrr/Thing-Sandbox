"""Base data types for LLM adapters.

Defines common response types used by all adapter implementations.
These types provide a unified interface for adapter responses.

Example:
    >>> from src.utils.llm_adapters.base import AdapterResponse, ResponseUsage
    >>> usage = ResponseUsage(input_tokens=100, output_tokens=50)
    >>> response = AdapterResponse(
    ...     response_id="resp_123",
    ...     parsed=MySchema(field="value"),
    ...     usage=usage,
    ... )
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class ResponseUsage:
    """Token usage statistics from API response.

    Tracks token consumption for billing and monitoring purposes.

    Example:
        >>> usage = ResponseUsage(input_tokens=100, output_tokens=50, reasoning_tokens=25)
        >>> usage.input_tokens
        100
    """

    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0


@dataclass
class AdapterResponse(Generic[T]):
    """Container for successful API response.

    Generic over Pydantic model type T. Contains the parsed response,
    usage statistics, and response ID for chaining.

    Example:
        >>> from pydantic import BaseModel
        >>> class MySchema(BaseModel):
        ...     answer: str
        >>> usage = ResponseUsage(input_tokens=10, output_tokens=5)
        >>> response = AdapterResponse(
        ...     response_id="resp_abc123",
        ...     parsed=MySchema(answer="42"),
        ...     usage=usage,
        ... )
        >>> response.parsed.answer
        '42'
    """

    response_id: str
    parsed: T
    usage: ResponseUsage
