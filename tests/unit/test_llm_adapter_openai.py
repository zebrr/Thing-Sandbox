"""Unit tests for OpenAI adapter with mocked API."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APITimeoutError, RateLimitError
from pydantic import BaseModel

from src.config import PhaseConfig
from src.utils.llm_adapters import OpenAIAdapter
from src.utils.llm_errors import (
    LLMError,
    LLMIncompleteError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)


class SimpleAnswer(BaseModel):
    """Simple test schema."""

    answer: str


class MathReasoning(BaseModel):
    """Complex test schema."""

    steps: list[str]
    final_answer: str


@pytest.fixture
def phase_config() -> PhaseConfig:
    """Create test phase config."""
    return PhaseConfig(
        model="gpt-test-model",
        is_reasoning=False,
        max_context_tokens=128000,
        max_completion=4096,
        timeout=60,
        max_retries=3,
        reasoning_effort=None,
        reasoning_summary=None,
        verbosity=None,
        truncation=None,
        response_chain_depth=0,
    )


@pytest.fixture
def reasoning_config() -> PhaseConfig:
    """Create test phase config with reasoning enabled."""
    return PhaseConfig(
        model="gpt-reasoning-model",
        is_reasoning=True,
        max_context_tokens=400000,
        max_completion=128000,
        timeout=600,
        max_retries=3,
        reasoning_effort="medium",
        reasoning_summary="auto",
        verbosity=None,
        truncation="auto",
        response_chain_depth=0,
    )


def create_mock_response(
    response_id: str = "resp_test123",
    status: str = "completed",
    output_parsed: BaseModel | None = None,
    content_type: str = "output_text",
    refusal: str | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
    reasoning_tokens: int = 0,
    incomplete_reason: str | None = None,
    error_message: str | None = None,
) -> MagicMock:
    """Create a mock OpenAI response object."""
    mock_response = MagicMock()
    mock_response.id = response_id
    mock_response.status = status
    mock_response.output_parsed = output_parsed

    # Create content mock
    content_mock = MagicMock()
    content_mock.type = content_type
    if refusal:
        content_mock.refusal = refusal

    # Create output mock
    output_mock = MagicMock()
    output_mock.content = [content_mock]
    mock_response.output = [output_mock]

    # Create usage mock
    usage_mock = MagicMock()
    usage_mock.input_tokens = input_tokens
    usage_mock.output_tokens = output_tokens

    details_mock = MagicMock()
    details_mock.reasoning_tokens = reasoning_tokens
    usage_mock.output_tokens_details = details_mock

    mock_response.usage = usage_mock

    # Incomplete details
    if incomplete_reason:
        incomplete_mock = MagicMock()
        incomplete_mock.reason = incomplete_reason
        mock_response.incomplete_details = incomplete_mock

    # Error
    if error_message:
        error_mock = MagicMock()
        error_mock.message = error_message
        mock_response.error = error_mock

    return mock_response


class TestOpenAIAdapterInit:
    """Tests for adapter initialization."""

    def test_init_without_api_key_raises(self, phase_config: PhaseConfig) -> None:
        """Raises LLMError if OPENAI_API_KEY not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(LLMError) as exc_info:
                OpenAIAdapter(phase_config)
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_init_with_api_key_succeeds(self, phase_config: PhaseConfig) -> None:
        """Creates adapter when API key is set."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)
            assert adapter.config == phase_config


class TestOpenAIAdapterExecuteSuccess:
    """Tests for successful execute calls."""

    @pytest.mark.asyncio
    async def test_successful_response(self, phase_config: PhaseConfig) -> None:
        """Returns AdapterResponse on successful request."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_response = create_mock_response(
                response_id="resp_success123",
                output_parsed=SimpleAnswer(answer="42"),
                input_tokens=100,
                output_tokens=50,
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_response)

            response = await adapter.execute(
                instructions="Answer briefly.",
                input_data="What is 6 * 7?",
                schema=SimpleAnswer,
            )

            assert response.response_id == "resp_success123"
            assert response.parsed.answer == "42"
            assert response.usage.input_tokens == 100
            assert response.usage.output_tokens == 50
            assert response.usage.reasoning_tokens == 0

    @pytest.mark.asyncio
    async def test_reasoning_tokens_extracted(
        self, reasoning_config: PhaseConfig
    ) -> None:
        """Extracts reasoning tokens for reasoning models."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(reasoning_config)

            mock_response = create_mock_response(
                output_parsed=SimpleAnswer(answer="42"),
                input_tokens=100,
                output_tokens=50,
                reasoning_tokens=25,
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_response)

            response = await adapter.execute(
                instructions="Think step by step.",
                input_data="What is 6 * 7?",
                schema=SimpleAnswer,
            )

            assert response.usage.reasoning_tokens == 25

    @pytest.mark.asyncio
    async def test_previous_response_id_passed(
        self, phase_config: PhaseConfig
    ) -> None:
        """Passes previous_response_id to API when provided."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_response = create_mock_response(
                output_parsed=SimpleAnswer(answer="Alice"),
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_response)

            await adapter.execute(
                instructions="Recall the name.",
                input_data="What was my name?",
                schema=SimpleAnswer,
                previous_response_id="resp_previous123",
            )

            call_kwargs = adapter.client.responses.parse.call_args.kwargs
            assert call_kwargs["previous_response_id"] == "resp_previous123"

    @pytest.mark.asyncio
    async def test_reasoning_params_passed_when_enabled(
        self, reasoning_config: PhaseConfig
    ) -> None:
        """Passes reasoning parameters when is_reasoning=True."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(reasoning_config)

            mock_response = create_mock_response(
                output_parsed=SimpleAnswer(answer="42"),
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_response)

            await adapter.execute(
                instructions="Think.",
                input_data="Question",
                schema=SimpleAnswer,
            )

            call_kwargs = adapter.client.responses.parse.call_args.kwargs
            assert "reasoning" in call_kwargs
            assert call_kwargs["reasoning"]["effort"] == "medium"
            assert call_kwargs["reasoning"]["summary"] == "auto"

    @pytest.mark.asyncio
    async def test_reasoning_params_not_passed_when_disabled(
        self, phase_config: PhaseConfig
    ) -> None:
        """Does not pass reasoning parameters when is_reasoning=False."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_response = create_mock_response(
                output_parsed=SimpleAnswer(answer="42"),
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_response)

            await adapter.execute(
                instructions="Answer.",
                input_data="Question",
                schema=SimpleAnswer,
            )

            call_kwargs = adapter.client.responses.parse.call_args.kwargs
            assert "reasoning" not in call_kwargs

    @pytest.mark.asyncio
    async def test_optional_params_passed_when_set(
        self, reasoning_config: PhaseConfig
    ) -> None:
        """Passes truncation and verbosity when set."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            # Modify config to include verbosity
            config = reasoning_config.model_copy()
            config.verbosity = "high"

            adapter = OpenAIAdapter(config)

            mock_response = create_mock_response(
                output_parsed=SimpleAnswer(answer="42"),
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_response)

            await adapter.execute(
                instructions="Answer.",
                input_data="Question",
                schema=SimpleAnswer,
            )

            call_kwargs = adapter.client.responses.parse.call_args.kwargs
            assert call_kwargs["truncation"] == "auto"
            assert call_kwargs["verbosity"] == "high"


class TestOpenAIAdapterRetryLogic:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_then_success(
        self, phase_config: PhaseConfig
    ) -> None:
        """Retries on rate limit and succeeds."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            # First call raises rate limit, second succeeds
            rate_limit_error = RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(
                    status_code=429,
                    headers=httpx.Headers({"x-ratelimit-reset-tokens": "100ms"}),
                ),
                body=None,
            )

            mock_success = create_mock_response(
                output_parsed=SimpleAnswer(answer="success"),
            )

            adapter.client.responses.parse = AsyncMock(
                side_effect=[rate_limit_error, mock_success]
            )

            with patch("asyncio.sleep", new_callable=AsyncMock):
                response = await adapter.execute(
                    instructions="Test",
                    input_data="Test",
                    schema=SimpleAnswer,
                )

            assert response.parsed.answer == "success"
            assert adapter.client.responses.parse.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_exhausted_raises(
        self, phase_config: PhaseConfig
    ) -> None:
        """Raises LLMRateLimitError after max retries."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            # Set max_retries to 2 for faster test
            config = phase_config.model_copy()
            config.max_retries = 2

            adapter = OpenAIAdapter(config)

            rate_limit_error = RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(
                    status_code=429,
                    headers=httpx.Headers({"x-ratelimit-reset-tokens": "100ms"}),
                ),
                body=None,
            )

            # Always raise rate limit error
            adapter.client.responses.parse = AsyncMock(side_effect=rate_limit_error)

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(LLMRateLimitError) as exc_info:
                    await adapter.execute(
                        instructions="Test",
                        input_data="Test",
                        schema=SimpleAnswer,
                    )

            assert "3 attempts" in str(exc_info.value)  # max_retries + 1
            assert adapter.client.responses.parse.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_timeout_then_success(
        self, phase_config: PhaseConfig
    ) -> None:
        """Retries on timeout and succeeds."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_success = create_mock_response(
                output_parsed=SimpleAnswer(answer="success"),
            )

            adapter.client.responses.parse = AsyncMock(
                side_effect=[httpx.TimeoutException("timeout"), mock_success]
            )

            with patch("asyncio.sleep", new_callable=AsyncMock):
                response = await adapter.execute(
                    instructions="Test",
                    input_data="Test",
                    schema=SimpleAnswer,
                )

            assert response.parsed.answer == "success"

    @pytest.mark.asyncio
    async def test_timeout_exhausted_raises(self, phase_config: PhaseConfig) -> None:
        """Raises LLMTimeoutError after max retries."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            config = phase_config.model_copy()
            config.max_retries = 1

            adapter = OpenAIAdapter(config)

            adapter.client.responses.parse = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(LLMTimeoutError) as exc_info:
                    await adapter.execute(
                        instructions="Test",
                        input_data="Test",
                        schema=SimpleAnswer,
                    )

            assert "2 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_timeout_error_handled(self, phase_config: PhaseConfig) -> None:
        """Handles OpenAI SDK APITimeoutError same as httpx.TimeoutException."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_success = create_mock_response(
                output_parsed=SimpleAnswer(answer="success"),
            )

            # APITimeoutError is what SDK actually raises
            adapter.client.responses.parse = AsyncMock(
                side_effect=[
                    APITimeoutError(request=MagicMock()),
                    mock_success,
                ]
            )

            with patch("asyncio.sleep", new_callable=AsyncMock):
                response = await adapter.execute(
                    instructions="Test",
                    input_data="Test",
                    schema=SimpleAnswer,
                )

            assert response.parsed.answer == "success"

    @pytest.mark.asyncio
    async def test_no_retry_on_refusal(self, phase_config: PhaseConfig) -> None:
        """Does not retry on refusal - raises immediately."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_refusal = create_mock_response(
                status="completed",
                output_parsed=None,
                content_type="refusal",
                refusal="I cannot assist with that request.",
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_refusal)

            with pytest.raises(LLMRefusalError) as exc_info:
                await adapter.execute(
                    instructions="Test",
                    input_data="Harmful content",
                    schema=SimpleAnswer,
                )

            assert "I cannot assist" in exc_info.value.refusal_message
            # Should only call once - no retry
            assert adapter.client.responses.parse.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_incomplete(self, phase_config: PhaseConfig) -> None:
        """Does not retry on incomplete - raises immediately."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_incomplete = create_mock_response(
                status="incomplete",
                output_parsed=None,
                incomplete_reason="max_output_tokens",
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_incomplete)

            with pytest.raises(LLMIncompleteError) as exc_info:
                await adapter.execute(
                    instructions="Test",
                    input_data="Long question",
                    schema=SimpleAnswer,
                )

            assert exc_info.value.reason == "max_output_tokens"
            assert adapter.client.responses.parse.call_count == 1


class TestOpenAIAdapterStatusHandling:
    """Tests for response status handling."""

    @pytest.mark.asyncio
    async def test_status_completed_success(self, phase_config: PhaseConfig) -> None:
        """Completed status returns successful response."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_response = create_mock_response(
                status="completed",
                output_parsed=SimpleAnswer(answer="done"),
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_response)

            response = await adapter.execute(
                instructions="Test",
                input_data="Test",
                schema=SimpleAnswer,
            )

            assert response.parsed.answer == "done"

    @pytest.mark.asyncio
    async def test_status_failed_raises(self, phase_config: PhaseConfig) -> None:
        """Failed status raises LLMError."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_failed = create_mock_response(
                status="failed",
                output_parsed=None,
                error_message="Internal server error",
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_failed)

            with pytest.raises(LLMError) as exc_info:
                await adapter.execute(
                    instructions="Test",
                    input_data="Test",
                    schema=SimpleAnswer,
                )

            assert "Internal server error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_status_incomplete_raises(self, phase_config: PhaseConfig) -> None:
        """Incomplete status raises LLMIncompleteError."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_incomplete = create_mock_response(
                status="incomplete",
                output_parsed=None,
                incomplete_reason="max_output_tokens",
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_incomplete)

            with pytest.raises(LLMIncompleteError) as exc_info:
                await adapter.execute(
                    instructions="Test",
                    input_data="Test",
                    schema=SimpleAnswer,
                )

            assert exc_info.value.reason == "max_output_tokens"

    @pytest.mark.asyncio
    async def test_refusal_content_raises(self, phase_config: PhaseConfig) -> None:
        """Refusal content type raises LLMRefusalError."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)

            mock_refusal = create_mock_response(
                status="completed",
                output_parsed=None,
                content_type="refusal",
                refusal="Cannot assist with harmful content",
            )

            adapter.client.responses.parse = AsyncMock(return_value=mock_refusal)

            with pytest.raises(LLMRefusalError) as exc_info:
                await adapter.execute(
                    instructions="Test",
                    input_data="Harmful",
                    schema=SimpleAnswer,
                )

            assert exc_info.value.refusal_message == "Cannot assist with harmful content"


class TestOpenAIAdapterDeleteResponse:
    """Tests for delete_response method."""

    @pytest.mark.asyncio
    async def test_delete_success(self, phase_config: PhaseConfig) -> None:
        """Returns True on successful deletion."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)
            adapter.client.responses.delete = AsyncMock(return_value=None)

            result = await adapter.delete_response("resp_to_delete")

            assert result is True
            adapter.client.responses.delete.assert_called_once_with("resp_to_delete")

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_false(
        self, phase_config: PhaseConfig
    ) -> None:
        """Returns False when response not found."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)
            adapter.client.responses.delete = AsyncMock(
                side_effect=Exception("Not found")
            )

            result = await adapter.delete_response("resp_nonexistent")

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_network_error_returns_false(
        self, phase_config: PhaseConfig
    ) -> None:
        """Returns False on network error, does not raise."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)
            adapter.client.responses.delete = AsyncMock(
                side_effect=httpx.NetworkError("Connection failed")
            )

            result = await adapter.delete_response("resp_123")

            assert result is False


class TestParseResetMs:
    """Tests for rate limit header parsing."""

    def test_parse_milliseconds(self, phase_config: PhaseConfig) -> None:
        """Parses milliseconds format correctly."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)
            headers = httpx.Headers({"x-ratelimit-reset-tokens": "1000ms"})

            result = adapter._parse_reset_ms(headers)

            assert result == 1.5  # 1000ms / 1000 + 0.5 buffer

    def test_parse_seconds(self, phase_config: PhaseConfig) -> None:
        """Parses seconds format correctly."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)
            headers = httpx.Headers({"x-ratelimit-reset-tokens": "2.5s"})

            result = adapter._parse_reset_ms(headers)

            assert result == 3.0  # 2.5s + 0.5 buffer

    def test_parse_missing_header_defaults(self, phase_config: PhaseConfig) -> None:
        """Uses default when header missing."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)
            headers = httpx.Headers({})

            result = adapter._parse_reset_ms(headers)

            assert result == 1.5  # Default 1000ms / 1000 + 0.5

    def test_parse_invalid_format_defaults(self, phase_config: PhaseConfig) -> None:
        """Uses default on parse error."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
            adapter = OpenAIAdapter(phase_config)
            headers = httpx.Headers({"x-ratelimit-reset-tokens": "invalid"})

            result = adapter._parse_reset_ms(headers)

            assert result == 1.5  # Default fallback
