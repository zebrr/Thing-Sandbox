"""Provider-agnostic LLM client facade.

Handles batch execution, response chains, and usage accumulation.
Phases work only with this interface.

Example:
    >>> from pydantic import BaseModel
    >>> from src.config import Config
    >>> from src.utils.llm import LLMClient, LLMRequest
    >>> from src.utils.llm_adapters import OpenAIAdapter
    >>>
    >>> class IntentionResponse(BaseModel):
    ...     intention: str
    ...     reasoning: str
    >>>
    >>> config = Config.load()
    >>> adapter = OpenAIAdapter(config.phase1)
    >>> client = LLMClient(
    ...     adapter=adapter,
    ...     entities=characters,
    ...     default_depth=config.phase1.response_chain_depth,
    ... )
    >>> result = await client.create_response(
    ...     instructions="Determine character intention.",
    ...     input_data=context,
    ...     schema=IntentionResponse,
    ...     entity_key="intention:bob",
    ... )
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pydantic import BaseModel

from src.utils.llm_adapters.base import AdapterResponse, ResponseUsage
from src.utils.llm_errors import LLMError

if TYPE_CHECKING:
    from src.utils.llm_adapters.openai import OpenAIAdapter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMRequest:
    """Request data for batch execution.

    Contains all information needed for a single LLM request,
    including optional entity binding for chain management.

    Example:
        >>> request = LLMRequest(
        ...     instructions="Answer briefly.",
        ...     input_data="What is 2+2?",
        ...     schema=SimpleAnswer,
        ...     entity_key="intention:bob",
        ... )
    """

    instructions: str
    input_data: str
    schema: type[BaseModel]
    entity_key: str | None = None
    depth_override: int | None = None


class ResponseChainManager:
    """Manages response chains stored in entities.

    Stateless helper that tracks response IDs in entity dictionaries.
    Supports sliding window eviction for chain depth management.

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

    Example:
        >>> entities = [{"identity": {"id": "bob"}, "state": {}}]
        >>> manager = ResponseChainManager(entities)
        >>> prev = manager.get_previous("intention:bob")
        >>> evicted = manager.confirm("intention:bob", "resp_123", depth=2)
    """

    def __init__(self, entities: list[dict[str, Any]]) -> None:
        """Build index of entities by ID.

        Args:
            entities: List of entity dictionaries. Each must have identity.id field.
                     Entities without valid ID are skipped.
        """
        self.entities: dict[str, dict[str, Any]] = {}
        for entity in entities:
            identity = entity.get("identity")
            if identity and isinstance(identity, dict):
                entity_id = identity.get("id")
                if entity_id:
                    self.entities[entity_id] = entity

    def get_previous(self, entity_key: str) -> str | None:
        """Get last response_id from chain.

        Args:
            entity_key: Key like "intention:bob", "memory:elvira".

        Returns:
            Last response_id in chain or None if chain is empty or entity not found.
        """
        entity_id, chain_name = self._parse_key(entity_key)
        entity = self.entities.get(entity_id)
        if not entity:
            logger.debug("Entity not found for key: %s", entity_key)
            return None

        openai_data = entity.get("_openai")
        if not openai_data:
            return None

        chain_key = f"{chain_name}_chain"
        chain = openai_data.get(chain_key)
        if not chain:
            return None

        logger.debug("Chain get_previous(%s) = %s", entity_key, chain[-1])
        return cast(str, chain[-1])

    def confirm(
        self,
        entity_key: str,
        response_id: str,
        depth: int,
    ) -> str | None:
        """Add response to chain with sliding window.

        Mutates entity in-place.

        Args:
            entity_key: Key like "intention:bob", "memory:elvira".
            response_id: Response ID from OpenAI.
            depth: Chain depth (0 = don't add, >0 = sliding window size).

        Returns:
            Evicted response_id (for deletion) or None.
        """
        if depth == 0:
            logger.debug("Chain confirm(%s) skipped: depth=0", entity_key)
            return None

        entity_id, chain_name = self._parse_key(entity_key)
        entity = self.entities.get(entity_id)
        if not entity:
            logger.debug("Entity not found for confirm: %s", entity_key)
            return None

        # Ensure _openai section exists
        if "_openai" not in entity:
            entity["_openai"] = {}

        chain_key = f"{chain_name}_chain"
        if chain_key not in entity["_openai"]:
            entity["_openai"][chain_key] = []

        chain = entity["_openai"][chain_key]
        evicted: str | None = None

        # Sliding window: evict oldest if at capacity
        if len(chain) >= depth:
            evicted = chain.pop(0)

        chain.append(response_id)

        logger.debug(
            "Chain confirm(%s, %s, depth=%d) = evicted:%s",
            entity_key,
            response_id,
            depth,
            evicted,
        )
        return evicted

    def _parse_key(self, entity_key: str) -> tuple[str, str]:
        """Parse entity_key into (entity_id, chain_name).

        Args:
            entity_key: Key like "intention:bob".

        Returns:
            Tuple of (entity_id, chain_name).
            "intention:bob" -> ("bob", "intention")
        """
        chain_name, entity_id = entity_key.split(":", 1)
        return entity_id, chain_name


class LLMClient:
    """Provider-agnostic facade for LLM requests.

    Created per-phase with corresponding adapter and entities.
    Handles chain management, usage accumulation, and batch execution.

    Example:
        >>> adapter = OpenAIAdapter(config.phase1)
        >>> client = LLMClient(
        ...     adapter=adapter,
        ...     entities=characters,
        ...     default_depth=config.phase1.response_chain_depth,
        ... )
        >>> result = await client.create_response(
        ...     instructions="Determine intention.",
        ...     input_data=context,
        ...     schema=IntentionResponse,
        ...     entity_key="intention:bob",
        ... )
    """

    def __init__(
        self,
        adapter: OpenAIAdapter,
        entities: list[dict[str, Any]],
        default_depth: int = 0,
    ) -> None:
        """Create client instance for a specific phase.

        Args:
            adapter: LLM provider adapter (OpenAIAdapter, etc.).
            entities: List of characters or locations (mutated in-place).
            default_depth: Default chain depth from PhaseConfig (0 = independent requests).
        """
        self.adapter = adapter
        self.chain_manager = ResponseChainManager(entities)
        self.default_depth = default_depth

    async def create_response(
        self,
        instructions: str,
        input_data: str,
        schema: type[T],
        entity_key: str | None = None,
    ) -> T:
        """Single request to LLM with structured output.

        Args:
            instructions: System prompt.
            input_data: User content (character context, location data, etc.).
            schema: Pydantic model class for structured output.
            entity_key: Key for response chain ("intention:bob"), None for independent request.

        Returns:
            Instance of schema with parsed response.

        Raises:
            LLMRefusalError: Model refused due to safety.
            LLMIncompleteError: Response truncated (max_output_tokens reached).
            LLMRateLimitError: Rate limit after all retries.
            LLMTimeoutError: Timeout after all retries.
            LLMError: Other API errors.
        """
        logger.debug("Executing single request for %s", entity_key or "standalone")

        # Get previous_response_id from chain if entity_key provided
        previous_id: str | None = None
        if entity_key:
            previous_id = self.chain_manager.get_previous(entity_key)

        # Execute via adapter
        response = await self.adapter.execute(
            instructions=instructions,
            input_data=input_data,
            schema=schema,
            previous_response_id=previous_id,
        )

        # Auto-confirm with default_depth
        if entity_key:
            evicted = self.chain_manager.confirm(
                entity_key, response.response_id, self.default_depth
            )
            if evicted:
                await self.adapter.delete_response(evicted)

            # Accumulate usage
            self._accumulate_usage(entity_key, response.usage)

        return response.parsed

    async def create_batch(
        self,
        requests: list[LLMRequest],
    ) -> list[BaseModel | LLMError]:
        """Batch of parallel requests.

        Executes all requests in parallel via asyncio.gather.
        Failed requests return LLMError instances instead of raising.

        Warning:
            Each entity_key should appear at most once in the batch.
            Multiple requests to the same entity may cause race conditions
            in chain management.

        Args:
            requests: List of LLMRequest objects.

        Returns:
            List of results in same order as requests.
            Successful requests return schema instances.
            Failed requests return LLMError instances.
        """
        if not requests:
            return []

        logger.debug("Executing batch of %d requests", len(requests))

        # Create tasks for all requests
        tasks = [self._execute_one(r) for r in requests]

        # Execute in parallel, capturing exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert to uniform result list
        return [self._process_result(req, res) for req, res in zip(requests, results)]

    async def _execute_one(self, request: LLMRequest) -> AdapterResponse[BaseModel]:
        """Execute single request with chain and usage handling.

        Args:
            request: LLMRequest to execute.

        Returns:
            AdapterResponse from adapter.

        Raises:
            LLMError subclasses on failure.
        """
        # Get previous_response_id from chain
        previous_id: str | None = None
        if request.entity_key:
            previous_id = self.chain_manager.get_previous(request.entity_key)

        # Execute via adapter
        response = await self.adapter.execute(
            instructions=request.instructions,
            input_data=request.input_data,
            schema=request.schema,
            previous_response_id=previous_id,
        )

        # Auto-confirm with appropriate depth
        if request.entity_key:
            depth = (
                request.depth_override if request.depth_override is not None else self.default_depth
            )
            evicted = self.chain_manager.confirm(request.entity_key, response.response_id, depth)
            if evicted:
                await self.adapter.delete_response(evicted)

            # Accumulate usage
            self._accumulate_usage(request.entity_key, response.usage)

        return response

    def _accumulate_usage(self, entity_key: str, usage: ResponseUsage) -> None:
        """Add usage stats to entity["_openai"]["usage"].

        Creates sections if missing. Increments counters for
        total_input_tokens, total_output_tokens, total_requests.

        Args:
            entity_key: Entity key like "intention:bob".
            usage: ResponseUsage from adapter.
        """
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

    def _process_result(
        self,
        request: LLMRequest,
        result: AdapterResponse[BaseModel] | BaseException,
    ) -> BaseModel | LLMError:
        """Convert gather result to return type.

        Args:
            request: Original request (for type info).
            result: Result from asyncio.gather (AdapterResponse or exception).

        Returns:
            Parsed model instance for success, LLMError for failure.
        """
        if isinstance(result, BaseException):
            if isinstance(result, LLMError):
                return result
            return LLMError(f"Unexpected error: {result}")
        return result.parsed
