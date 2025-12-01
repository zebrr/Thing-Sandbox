"""OpenAI Responses API adapter.

Executes requests with retry logic, timeout handling, and structured
output parsing via Pydantic models.

Example:
    >>> from pydantic import BaseModel
    >>> from src.config import Config
    >>> from src.utils.llm_adapters import OpenAIAdapter
    >>>
    >>> class SimpleAnswer(BaseModel):
    ...     answer: str
    >>>
    >>> config = Config.load()
    >>> adapter = OpenAIAdapter(config.phase1)
    >>> response = await adapter.execute(
    ...     instructions="Answer briefly.",
    ...     input_data="What is 2+2?",
    ...     schema=SimpleAnswer,
    ... )
    >>> response.parsed.answer
    '4'
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, TypeVar

import httpx
from openai import APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from src.utils.llm_adapters.base import AdapterResponse, ResponseUsage
from src.utils.llm_errors import (
    LLMError,
    LLMIncompleteError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)

if TYPE_CHECKING:
    from src.config import PhaseConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAIAdapter:
    """Adapter for OpenAI Responses API.

    Stateless adapter that executes requests with automatic retry
    for rate limits and timeouts. Create per-request with phase configuration.

    Example:
        >>> from src.config import Config
        >>> config = Config.load()
        >>> adapter = OpenAIAdapter(config.phase1)
    """

    def __init__(self, config: PhaseConfig) -> None:
        """Create adapter instance with phase configuration.

        Args:
            config: Phase configuration with model, timeout, retry settings.

        Raises:
            LLMError: If OPENAI_API_KEY environment variable is not set.
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise LLMError("OPENAI_API_KEY environment variable not set")

        timeout = httpx.Timeout(float(config.timeout), connect=10.0)
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.config = config

    async def execute(
        self,
        instructions: str,
        input_data: str,
        schema: type[T],
        previous_response_id: str | None = None,
    ) -> AdapterResponse[T]:
        """Execute single request to OpenAI API with structured output.

        Args:
            instructions: System prompt.
            input_data: User content (character context, location data, etc.).
            schema: Pydantic model class for structured output.
            previous_response_id: For response chain continuity, default None.

        Returns:
            AdapterResponse with parsed response, usage stats, and response_id.

        Raises:
            LLMRefusalError: Model refused due to safety.
            LLMIncompleteError: Response truncated (max_output_tokens reached).
            LLMRateLimitError: Rate limit after all retries exhausted.
            LLMTimeoutError: Timeout after all retries exhausted.
            LLMError: Other API errors (invalid model, broken chain, etc.).
        """
        max_retries = self.config.max_retries

        for attempt in range(max_retries + 1):
            try:
                logger.debug(
                    "Executing request to %s (attempt %d/%d)",
                    self.config.model,
                    attempt + 1,
                    max_retries + 1,
                )
                response = await self._do_request(
                    instructions, input_data, schema, previous_response_id
                )
                return self._process_response(response, schema)

            except RateLimitError as e:
                if attempt >= max_retries:
                    logger.error("Rate limit exhausted after %d attempts", attempt + 1)
                    raise LLMRateLimitError(f"Rate limit after {attempt + 1} attempts") from e
                wait = self._parse_reset_ms(e.response.headers)
                logger.warning(
                    "Rate limit hit, waiting %.1fs (attempt %d/%d)",
                    wait,
                    attempt + 1,
                    max_retries + 1,
                )
                await asyncio.sleep(wait)

            except (httpx.TimeoutException, APITimeoutError) as e:
                if attempt >= max_retries:
                    logger.error("Timeout exhausted after %d attempts", attempt + 1)
                    raise LLMTimeoutError(f"Timeout after {attempt + 1} attempts") from e
                logger.warning(
                    "Timeout, retrying (attempt %d/%d)",
                    attempt + 1,
                    max_retries + 1,
                )
                await asyncio.sleep(1.0)

            except (LLMRefusalError, LLMIncompleteError):
                # No retry for refusal and incomplete - raise immediately
                raise

            except Exception as e:
                # Wrap unexpected errors
                logger.error("Unexpected error during request: %s", e)
                raise LLMError(f"Request failed: {e}") from e

        # Should not reach here, but satisfy type checker
        raise LLMError("Request failed: unknown error")

    async def _do_request(
        self,
        instructions: str,
        input_data: str,
        schema: type[T],
        previous_response_id: str | None,
    ) -> object:
        """Execute single request to OpenAI API.

        Args:
            instructions: System prompt.
            input_data: User content.
            schema: Pydantic model class.
            previous_response_id: Previous response ID for chaining.

        Returns:
            Raw response object from OpenAI SDK.
        """
        # Build request parameters
        params: dict[str, object] = {
            "model": self.config.model,
            "instructions": instructions,
            "input": input_data,
            "text_format": schema,
            "max_output_tokens": self.config.max_completion,
            "store": True,
        }

        # Add previous_response_id if provided
        if previous_response_id:
            params["previous_response_id"] = previous_response_id

        # Add reasoning parameters only if is_reasoning is True
        if self.config.is_reasoning:
            reasoning: dict[str, str] = {}
            if self.config.reasoning_effort:
                reasoning["effort"] = self.config.reasoning_effort
            if self.config.reasoning_summary:
                reasoning["summary"] = self.config.reasoning_summary
            if reasoning:
                params["reasoning"] = reasoning

        # Add optional parameters only if set
        if self.config.truncation:
            params["truncation"] = self.config.truncation
        if self.config.verbosity:
            params["verbosity"] = self.config.verbosity

        return await self.client.responses.parse(**params)  # type: ignore[arg-type]

    def _process_response(self, response: object, schema: type[T]) -> AdapterResponse[T]:
        """Process OpenAI response and extract data.

        Args:
            response: Raw response from OpenAI SDK.
            schema: Expected Pydantic model type.

        Returns:
            AdapterResponse with parsed data.

        Raises:
            LLMIncompleteError: If response status is incomplete.
            LLMRefusalError: If model refused the request.
            LLMError: If response status is failed or other error.
        """
        # Check response status
        status = getattr(response, "status", None)

        if status == "incomplete":
            incomplete_details = getattr(response, "incomplete_details", None)
            reason = "unknown"
            if incomplete_details:
                reason = getattr(incomplete_details, "reason", "unknown")
            logger.error("Response incomplete: %s", reason)
            raise LLMIncompleteError(reason)

        if status == "failed":
            error = getattr(response, "error", None)
            message = getattr(error, "message", "unknown error") if error else "unknown error"
            logger.error("Response failed: %s", message)
            raise LLMError(f"Request failed: {message}")

        # Check for refusal in output content
        output = getattr(response, "output", [])
        if output:
            first_output = output[0]
            content_list = getattr(first_output, "content", [])
            if content_list:
                first_content = content_list[0]
                content_type = getattr(first_content, "type", None)
                if content_type == "refusal":
                    refusal_msg = getattr(first_content, "refusal", "Unknown refusal")
                    logger.warning("Model refused request: %s", refusal_msg)
                    raise LLMRefusalError(refusal_msg)

        # Extract parsed output
        output_parsed = getattr(response, "output_parsed", None)
        if output_parsed is None:
            raise LLMError("Response has no parsed output")

        # Extract usage statistics
        usage_obj = getattr(response, "usage", None)
        if usage_obj is None:
            raise LLMError("Response has no usage information")

        input_tokens = getattr(usage_obj, "input_tokens", 0)
        output_tokens = getattr(usage_obj, "output_tokens", 0)

        # Extract reasoning tokens from details
        output_tokens_details = getattr(usage_obj, "output_tokens_details", None)
        reasoning_tokens = 0
        if output_tokens_details:
            reasoning_tokens = getattr(output_tokens_details, "reasoning_tokens", 0) or 0

        usage = ResponseUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
        )

        response_id = getattr(response, "id", "")
        logger.debug(
            "Response received: id=%s, input=%d, output=%d, reasoning=%d",
            response_id,
            input_tokens,
            output_tokens,
            reasoning_tokens,
        )

        return AdapterResponse(
            response_id=response_id,
            parsed=output_parsed,
            usage=usage,
        )

    def _parse_reset_ms(self, headers: httpx.Headers) -> float:
        """Parse reset time from rate limit headers.

        Args:
            headers: HTTP response headers.

        Returns:
            Wait time in seconds with 0.5s buffer.
        """
        reset_str = headers.get("x-ratelimit-reset-tokens", "1000ms")
        try:
            # Handle formats like "1000ms" or "1.5s"
            if reset_str.endswith("ms"):
                ms = int(reset_str.rstrip("ms"))
                return ms / 1000 + 0.5
            elif reset_str.endswith("s"):
                seconds = float(reset_str.rstrip("s"))
                return seconds + 0.5
            else:
                # Assume milliseconds if no unit
                ms = int(reset_str)
                return ms / 1000 + 0.5
        except (ValueError, TypeError):
            logger.warning("Could not parse reset header: %s, using 1s default", reset_str)
            return 1.5

    async def delete_response(self, response_id: str) -> bool:
        """Delete response from OpenAI storage.

        Used for chain cleanup. Errors are logged but not raised.

        Args:
            response_id: ID of response to delete.

        Returns:
            True if deleted successfully, False on error.
        """
        try:
            await self.client.responses.delete(response_id)
            logger.debug("Deleted response: %s", response_id)
            return True
        except Exception as e:
            logger.warning("Failed to delete response %s: %s", response_id, e)
            return False
