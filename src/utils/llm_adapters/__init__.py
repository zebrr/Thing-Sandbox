"""LLM adapters package.

Provides adapter implementations for various LLM providers.
Currently supports OpenAI Responses API.

Example:
    >>> from src.utils.llm_adapters import OpenAIAdapter, AdapterResponse, ResponseUsage
    >>> from src.config import Config
    >>>
    >>> config = Config.load()
    >>> adapter = OpenAIAdapter(config.phase1)
"""

from src.utils.llm_adapters.base import (
    AdapterResponse,
    ResponseDebugInfo,
    ResponseUsage,
)
from src.utils.llm_adapters.openai import OpenAIAdapter

__all__ = ["AdapterResponse", "ResponseDebugInfo", "ResponseUsage", "OpenAIAdapter"]
