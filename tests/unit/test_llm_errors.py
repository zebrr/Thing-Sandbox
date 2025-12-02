"""Unit tests for LLM error hierarchy and data types."""

import pytest
from pydantic import BaseModel

from src.utils.llm_errors import (
    LLMError,
    LLMIncompleteError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)
from src.utils.llm_adapters.base import (
    AdapterResponse,
    ResponseDebugInfo,
    ResponseUsage,
)


class TestLLMErrorHierarchy:
    """Tests for exception hierarchy."""

    def test_llm_error_base(self) -> None:
        """Base exception can be raised with message."""
        with pytest.raises(LLMError) as exc_info:
            raise LLMError("Generic LLM failure")

        assert "Generic LLM failure" in str(exc_info.value)

    def test_llm_error_is_exception(self) -> None:
        """LLMError inherits from Exception."""
        error = LLMError("test")
        assert isinstance(error, Exception)

    def test_all_errors_inherit_from_llm_error(self) -> None:
        """All LLM exceptions inherit from LLMError."""
        errors = [
            LLMRefusalError("refusal"),
            LLMIncompleteError("reason"),
            LLMRateLimitError("rate limit"),
            LLMTimeoutError("timeout"),
        ]

        for error in errors:
            assert isinstance(error, LLMError)
            assert isinstance(error, Exception)

    def test_catch_all_llm_errors_with_base(self) -> None:
        """Can catch all LLM errors with single except clause."""
        errors_to_test = [
            LLMRefusalError("refused"),
            LLMIncompleteError("truncated"),
            LLMRateLimitError("rate limited"),
            LLMTimeoutError("timed out"),
            LLMError("generic"),
        ]

        for error in errors_to_test:
            try:
                raise error
            except LLMError as caught:
                assert caught is error


class TestLLMRefusalError:
    """Tests for LLMRefusalError."""

    def test_stores_refusal_message(self) -> None:
        """Refusal message is stored as attribute."""
        error = LLMRefusalError("I cannot assist with that request")
        assert error.refusal_message == "I cannot assist with that request"

    def test_message_format(self) -> None:
        """Error message includes 'Model refused:' prefix."""
        error = LLMRefusalError("Content policy violation")
        assert str(error) == "Model refused: Content policy violation"

    def test_unicode_refusal_message(self) -> None:
        """Handles non-ASCII refusal messages."""
        error = LLMRefusalError("Не могу помочь с этим запросом 🚫")
        assert error.refusal_message == "Не могу помочь с этим запросом 🚫"
        assert "Не могу помочь" in str(error)


class TestLLMIncompleteError:
    """Tests for LLMIncompleteError."""

    def test_stores_reason(self) -> None:
        """Reason is stored as attribute."""
        error = LLMIncompleteError("max_output_tokens")
        assert error.reason == "max_output_tokens"

    def test_message_format(self) -> None:
        """Error message includes 'Response incomplete:' prefix."""
        error = LLMIncompleteError("max_output_tokens")
        assert str(error) == "Response incomplete: max_output_tokens"

    def test_various_reasons(self) -> None:
        """Handles various truncation reasons."""
        reasons = ["max_output_tokens", "content_filter", "unknown"]
        for reason in reasons:
            error = LLMIncompleteError(reason)
            assert error.reason == reason


class TestLLMRateLimitError:
    """Tests for LLMRateLimitError."""

    def test_message_preserved(self) -> None:
        """Message is preserved in error."""
        error = LLMRateLimitError("Rate limit after 4 attempts")
        assert str(error) == "Rate limit after 4 attempts"

    def test_inherits_from_llm_error(self) -> None:
        """Inherits from LLMError."""
        error = LLMRateLimitError("test")
        assert isinstance(error, LLMError)


class TestLLMTimeoutError:
    """Tests for LLMTimeoutError."""

    def test_message_preserved(self) -> None:
        """Message is preserved in error."""
        error = LLMTimeoutError("Timeout after 4 attempts")
        assert str(error) == "Timeout after 4 attempts"

    def test_inherits_from_llm_error(self) -> None:
        """Inherits from LLMError."""
        error = LLMTimeoutError("test")
        assert isinstance(error, LLMError)


class TestResponseUsage:
    """Tests for ResponseUsage dataclass."""

    def test_basic_creation(self) -> None:
        """Can create with required fields."""
        usage = ResponseUsage(input_tokens=100, output_tokens=50)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.reasoning_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.total_tokens == 0

    def test_reasoning_tokens_default(self) -> None:
        """Reasoning tokens defaults to 0."""
        usage = ResponseUsage(input_tokens=100, output_tokens=50)
        assert usage.reasoning_tokens == 0

    def test_with_reasoning_tokens(self) -> None:
        """Can specify reasoning tokens."""
        usage = ResponseUsage(input_tokens=100, output_tokens=50, reasoning_tokens=25)
        assert usage.reasoning_tokens == 25

    def test_with_cached_tokens(self) -> None:
        """Can specify cached tokens."""
        usage = ResponseUsage(input_tokens=100, output_tokens=50, cached_tokens=80)
        assert usage.cached_tokens == 80

    def test_with_total_tokens(self) -> None:
        """Can specify total tokens."""
        usage = ResponseUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        assert usage.total_tokens == 150

    def test_zero_tokens(self) -> None:
        """Handles zero token counts."""
        usage = ResponseUsage(input_tokens=0, output_tokens=0, reasoning_tokens=0)
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.reasoning_tokens == 0

    def test_large_token_counts(self) -> None:
        """Handles large token counts."""
        usage = ResponseUsage(
            input_tokens=1_000_000,
            output_tokens=500_000,
            reasoning_tokens=100_000,
            cached_tokens=800_000,
            total_tokens=1_500_000,
        )
        assert usage.input_tokens == 1_000_000
        assert usage.output_tokens == 500_000
        assert usage.reasoning_tokens == 100_000
        assert usage.cached_tokens == 800_000
        assert usage.total_tokens == 1_500_000


class TestResponseDebugInfo:
    """Tests for ResponseDebugInfo dataclass."""

    def test_basic_creation(self) -> None:
        """Can create with required fields."""
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)
        assert debug.model == "gpt-4o"
        assert debug.created_at == 1700000000
        assert debug.service_tier is None
        assert debug.reasoning_summary is None

    def test_with_service_tier(self) -> None:
        """Can specify service tier."""
        debug = ResponseDebugInfo(
            model="gpt-4o", created_at=1700000000, service_tier="default"
        )
        assert debug.service_tier == "default"

    def test_with_reasoning_summary(self) -> None:
        """Can specify reasoning summary."""
        debug = ResponseDebugInfo(
            model="gpt-4o",
            created_at=1700000000,
            reasoning_summary=["Step 1: analyze", "Step 2: conclude"],
        )
        assert debug.reasoning_summary is not None
        assert len(debug.reasoning_summary) == 2
        assert "analyze" in debug.reasoning_summary[0]

    def test_all_fields(self) -> None:
        """Can specify all fields."""
        debug = ResponseDebugInfo(
            model="gpt-4o-2024-11-20",
            created_at=1700000000,
            service_tier="priority",
            reasoning_summary=["Thinking..."],
        )
        assert debug.model == "gpt-4o-2024-11-20"
        assert debug.created_at == 1700000000
        assert debug.service_tier == "priority"
        assert debug.reasoning_summary == ["Thinking..."]


class TestAdapterResponse:
    """Tests for AdapterResponse dataclass."""

    class SimpleSchema(BaseModel):
        """Simple test schema."""

        answer: str

    class ComplexSchema(BaseModel):
        """Complex test schema with nested fields."""

        text: str
        number: int
        items: list[str]

    def test_basic_creation(self) -> None:
        """Can create with Pydantic model."""
        usage = ResponseUsage(input_tokens=10, output_tokens=5)
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)
        parsed = self.SimpleSchema(answer="42")
        response = AdapterResponse(
            response_id="resp_abc123",
            parsed=parsed,
            usage=usage,
            debug=debug,
        )
        assert response.response_id == "resp_abc123"
        assert response.parsed.answer == "42"
        assert response.usage.input_tokens == 10
        assert response.debug.model == "gpt-4o"

    def test_generic_typing(self) -> None:
        """Works with different Pydantic model types."""
        usage = ResponseUsage(input_tokens=10, output_tokens=5)
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)

        # Simple schema
        simple_response: AdapterResponse[self.SimpleSchema] = AdapterResponse(
            response_id="resp_1",
            parsed=self.SimpleSchema(answer="test"),
            usage=usage,
            debug=debug,
        )
        assert simple_response.parsed.answer == "test"

        # Complex schema
        complex_response: AdapterResponse[self.ComplexSchema] = AdapterResponse(
            response_id="resp_2",
            parsed=self.ComplexSchema(text="hello", number=42, items=["a", "b"]),
            usage=usage,
            debug=debug,
        )
        assert complex_response.parsed.text == "hello"
        assert complex_response.parsed.number == 42
        assert complex_response.parsed.items == ["a", "b"]

    def test_response_id_format(self) -> None:
        """Response ID can be any string."""
        usage = ResponseUsage(input_tokens=10, output_tokens=5)
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)
        parsed = self.SimpleSchema(answer="test")

        # Various ID formats
        ids = [
            "resp_abc123",
            "resp_xyz789def456",
            "response-id-with-dashes",
            "Ответ_123_кириллица",
        ]

        for resp_id in ids:
            response = AdapterResponse(
                response_id=resp_id,
                parsed=parsed,
                usage=usage,
                debug=debug,
            )
            assert response.response_id == resp_id

    def test_unicode_content(self) -> None:
        """Handles unicode content in parsed response."""
        usage = ResponseUsage(input_tokens=10, output_tokens=5)
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)
        parsed = self.SimpleSchema(answer="Привет, мир! 🌍")
        response = AdapterResponse(
            response_id="resp_unicode",
            parsed=parsed,
            usage=usage,
            debug=debug,
        )
        assert response.parsed.answer == "Привет, мир! 🌍"
