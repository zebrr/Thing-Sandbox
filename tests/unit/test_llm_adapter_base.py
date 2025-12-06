"""Unit tests for utils/llm_adapters/base module."""

from pydantic import BaseModel

from src.utils.llm_adapters.base import (
    AdapterResponse,
    ResponseDebugInfo,
    ResponseUsage,
)


class SampleSchema(BaseModel):
    """Sample Pydantic model for testing AdapterResponse."""

    answer: str
    confidence: float = 0.9


class TestResponseUsage:
    """Tests for ResponseUsage dataclass."""

    def test_response_usage_required_fields(self) -> None:
        """ResponseUsage requires input_tokens and output_tokens."""
        usage = ResponseUsage(input_tokens=100, output_tokens=50)

        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    def test_response_usage_defaults(self) -> None:
        """ResponseUsage optional fields default to 0."""
        usage = ResponseUsage(input_tokens=100, output_tokens=50)

        assert usage.reasoning_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.total_tokens == 0

    def test_response_usage_all_fields(self) -> None:
        """ResponseUsage accepts all fields."""
        usage = ResponseUsage(
            input_tokens=1000,
            output_tokens=200,
            reasoning_tokens=150,
            cached_tokens=500,
            total_tokens=1200,
        )

        assert usage.input_tokens == 1000
        assert usage.output_tokens == 200
        assert usage.reasoning_tokens == 150
        assert usage.cached_tokens == 500
        assert usage.total_tokens == 1200

    def test_response_usage_equality(self) -> None:
        """Two ResponseUsage with same values are equal."""
        usage1 = ResponseUsage(input_tokens=100, output_tokens=50)
        usage2 = ResponseUsage(input_tokens=100, output_tokens=50)

        assert usage1 == usage2


class TestResponseDebugInfo:
    """Tests for ResponseDebugInfo dataclass."""

    def test_response_debug_info_required_fields(self) -> None:
        """ResponseDebugInfo requires model and created_at."""
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)

        assert debug.model == "gpt-4o"
        assert debug.created_at == 1700000000

    def test_response_debug_info_optional_fields_default_none(self) -> None:
        """ResponseDebugInfo optional fields default to None."""
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)

        assert debug.service_tier is None
        assert debug.reasoning_summary is None

    def test_response_debug_info_all_fields(self) -> None:
        """ResponseDebugInfo accepts all fields."""
        debug = ResponseDebugInfo(
            model="o1-preview",
            created_at=1700000000,
            service_tier="default",
            reasoning_summary=["Step 1", "Step 2"],
        )

        assert debug.model == "o1-preview"
        assert debug.created_at == 1700000000
        assert debug.service_tier == "default"
        assert debug.reasoning_summary == ["Step 1", "Step 2"]

    def test_response_debug_info_non_ascii_model(self) -> None:
        """ResponseDebugInfo handles non-ASCII in model name."""
        debug = ResponseDebugInfo(model="модель-тест", created_at=1700000000)

        assert debug.model == "модель-тест"


class TestAdapterResponse:
    """Tests for AdapterResponse generic dataclass."""

    def test_adapter_response_with_pydantic_model(self) -> None:
        """AdapterResponse stores parsed Pydantic model."""
        usage = ResponseUsage(input_tokens=100, output_tokens=50)
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)
        parsed = SampleSchema(answer="42")

        response: AdapterResponse[SampleSchema] = AdapterResponse(
            response_id="resp_abc123",
            parsed=parsed,
            usage=usage,
            debug=debug,
        )

        assert response.response_id == "resp_abc123"
        assert response.parsed == parsed
        assert response.usage == usage
        assert response.debug == debug

    def test_adapter_response_access_parsed_fields(self) -> None:
        """AdapterResponse.parsed fields are accessible."""
        usage = ResponseUsage(input_tokens=10, output_tokens=5)
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)
        parsed = SampleSchema(answer="test answer", confidence=0.95)

        response: AdapterResponse[SampleSchema] = AdapterResponse(
            response_id="resp_xyz",
            parsed=parsed,
            usage=usage,
            debug=debug,
        )

        assert response.parsed.answer == "test answer"
        assert response.parsed.confidence == 0.95

    def test_adapter_response_non_ascii_content(self) -> None:
        """AdapterResponse handles non-ASCII in parsed content."""
        usage = ResponseUsage(input_tokens=10, output_tokens=5)
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)
        parsed = SampleSchema(answer="Ответ на русском 你好")

        response: AdapterResponse[SampleSchema] = AdapterResponse(
            response_id="resp_123",
            parsed=parsed,
            usage=usage,
            debug=debug,
        )

        assert response.parsed.answer == "Ответ на русском 你好"

    def test_adapter_response_equality(self) -> None:
        """Two AdapterResponses with same values are equal."""
        usage = ResponseUsage(input_tokens=10, output_tokens=5)
        debug = ResponseDebugInfo(model="gpt-4o", created_at=1700000000)
        parsed = SampleSchema(answer="same")

        response1: AdapterResponse[SampleSchema] = AdapterResponse(
            response_id="resp_1",
            parsed=parsed,
            usage=usage,
            debug=debug,
        )
        response2: AdapterResponse[SampleSchema] = AdapterResponse(
            response_id="resp_1",
            parsed=parsed,
            usage=usage,
            debug=debug,
        )

        assert response1 == response2
