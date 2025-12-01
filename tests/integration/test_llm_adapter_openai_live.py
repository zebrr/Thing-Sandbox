"""Integration tests for OpenAI adapter with real API.

These tests require OPENAI_API_KEY environment variable to be set.
They make real API calls and may incur costs.

Run with: pytest tests/integration/test_llm_adapter_openai_live.py -v
"""

import os

import pytest
from pydantic import BaseModel

from src.config import Config
from src.utils.llm_adapters import OpenAIAdapter
from src.utils.llm_errors import LLMIncompleteError, LLMTimeoutError, LLMError


pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]


# Test schemas
class SimpleAnswer(BaseModel):
    """Simple schema for basic tests."""

    answer: str


class MathStep(BaseModel):
    """Single step in math reasoning."""

    explanation: str
    output: str


class MathReasoning(BaseModel):
    """Complex schema with nested fields."""

    steps: list[MathStep]
    final_answer: str


@pytest.fixture
def integration_config():
    """Configuration for integration tests - uses phase1 from config."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    config = Config.load()
    return config.phase1


@pytest.fixture
def adapter(integration_config):
    """Create adapter with integration config."""
    return OpenAIAdapter(integration_config)


class TestSimpleStructuredOutput:
    """Tests for basic structured output."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_simple_structured_output(self, adapter: OpenAIAdapter) -> None:
        """Test simple structured output request."""
        response = await adapter.execute(
            instructions="Answer briefly.",
            input_data="What is 2+2? Answer with just the number.",
            schema=SimpleAnswer,
        )

        assert response.parsed is not None
        assert "4" in response.parsed.answer
        assert response.response_id.startswith("resp_")
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_unicode_content(self, adapter: OpenAIAdapter) -> None:
        """Test handling of unicode content."""
        response = await adapter.execute(
            instructions="Ответь кратко на русском языке.",
            input_data="Какой город является столицей Франции?",
            schema=SimpleAnswer,
        )

        assert response.parsed is not None
        # Response should mention Paris in some form
        answer_lower = response.parsed.answer.lower()
        assert "париж" in answer_lower or "paris" in answer_lower


class TestComplexStructuredOutput:
    """Tests for complex nested schemas."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_complex_structured_output(self, adapter: OpenAIAdapter) -> None:
        """Test complex structured output with nested schema."""
        response = await adapter.execute(
            instructions="You are a helpful math tutor. Guide the user through the solution step by step.",
            input_data="How can I solve 8x + 7 = -23?",
            schema=MathReasoning,
        )

        assert response.parsed is not None
        assert len(response.parsed.steps) > 0
        assert response.parsed.final_answer is not None
        # Solution: 8x = -30, x = -30/8 = -3.75 or -15/4
        assert "-" in response.parsed.final_answer  # Answer is negative


class TestDeleteResponse:
    """Tests for response deletion."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_delete_response(self, adapter: OpenAIAdapter) -> None:
        """Test deleting a response."""
        # Create response
        response = await adapter.execute(
            instructions="Answer briefly.",
            input_data="Say hello.",
            schema=SimpleAnswer,
        )
        response_id = response.response_id

        # Delete
        result = await adapter.delete_response(response_id)
        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_delete_nonexistent_response(self, adapter: OpenAIAdapter) -> None:
        """Test deleting a nonexistent response returns False."""
        result = await adapter.delete_response("resp_nonexistent_12345")
        assert result is False


class TestIncompleteResponse:
    """Tests for incomplete response handling."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_incomplete_response(self, integration_config) -> None:
        """Test handling of incomplete response due to token limit."""
        # Create config with small token limit
        limited_config = integration_config.model_copy()
        limited_config.max_completion = 50  # Very small limit

        adapter = OpenAIAdapter(limited_config)

        with pytest.raises(LLMIncompleteError) as exc_info:
            await adapter.execute(
                instructions="You are a helpful math tutor. Solve with detailed step-by-step proof.",
                input_data=(
                    "Prove that there are infinitely many prime numbers. "
                    "Show complete formal proof with all steps explained in detail."
                ),
                schema=MathReasoning,
            )

        # The error reason should indicate max tokens was reached
        assert exc_info.value.reason is not None


class TestTimeout:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_timeout(self, integration_config) -> None:
        """Test timeout handling with short timeout."""
        # Create config with very short timeout
        timeout_config = integration_config.model_copy()
        timeout_config.timeout = 1  # 1 second - very short
        timeout_config.max_retries = 0  # No retry for clean test

        adapter = OpenAIAdapter(timeout_config)

        with pytest.raises(LLMTimeoutError) as exc_info:
            await adapter.execute(
                instructions="Think carefully step by step. Be extremely thorough.",
                input_data=(
                    "Explain the history of mathematics from ancient times "
                    "to modern day. Include all major developments."
                ),
                schema=MathReasoning,
            )

        error_msg = str(exc_info.value).lower()
        assert "timeout" in error_msg or "1" in error_msg


class TestPreviousResponseId:
    """Tests for response chaining."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_previous_response_id(self, adapter: OpenAIAdapter) -> None:
        """Test that previous_response_id passes context."""
        # First request
        response1 = await adapter.execute(
            instructions="Remember the user's name.",
            input_data="My name is Алиса. What is 2+2?",
            schema=SimpleAnswer,
        )
        assert "4" in response1.parsed.answer

        # Second request with previous_response_id
        response2 = await adapter.execute(
            instructions="Recall information from context.",
            input_data="What was my name?",
            schema=SimpleAnswer,
            previous_response_id=response1.response_id,
        )
        # Should remember the name from first request
        answer_lower = response2.parsed.answer.lower()
        assert "алиса" in answer_lower or "alice" in answer_lower or "alisa" in answer_lower

        # Cleanup
        await adapter.delete_response(response1.response_id)
        await adapter.delete_response(response2.response_id)


class TestReasoningModel:
    """Tests for reasoning model features."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_reasoning_model(self, integration_config) -> None:
        """Test reasoning model produces reasoning tokens."""
        if not integration_config.is_reasoning:
            pytest.skip("Test requires reasoning model (is_reasoning=True)")

        adapter = OpenAIAdapter(integration_config)

        response = await adapter.execute(
            instructions="Solve the math problem.",
            input_data="What is 123 * 456?",
            schema=SimpleAnswer,
        )

        assert response.parsed is not None
        # 123 * 456 = 56088
        assert "56088" in response.parsed.answer or "56,088" in response.parsed.answer
        # Reasoning models should use reasoning tokens
        assert response.usage.reasoning_tokens > 0


class TestErrorHandling:
    """Tests for error conditions."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_error_invalid_api_key(self, integration_config) -> None:
        """Test error handling with invalid API key."""
        # Temporarily replace API key
        original_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "sk-invalid-key-12345"

        try:
            bad_config = integration_config.model_copy()
            bad_config.max_retries = 0
            adapter = OpenAIAdapter(bad_config)

            with pytest.raises(LLMError) as exc_info:
                await adapter.execute(
                    instructions="Test",
                    input_data="Test",
                    schema=SimpleAnswer,
                )

            error_msg = str(exc_info.value).lower()
            assert (
                "auth" in error_msg
                or "invalid" in error_msg
                or "api" in error_msg
                or "key" in error_msg
            )
        finally:
            # Restore original key
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key


class TestUsageTracking:
    """Tests for usage statistics."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_usage_tracking(self, adapter: OpenAIAdapter) -> None:
        """Test that usage statistics are tracked correctly."""
        response = await adapter.execute(
            instructions="Answer briefly.",
            input_data="What color is the sky?",
            schema=SimpleAnswer,
        )

        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0
        # reasoning_tokens may be 0 for non-reasoning models
        assert response.usage.reasoning_tokens >= 0
