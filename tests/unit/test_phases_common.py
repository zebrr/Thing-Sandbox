"""Unit tests for phases/common module."""

from src.phases.common import PhaseResult
from src.utils.llm import BatchStats, RequestResult
from src.utils.llm_adapters.base import ResponseUsage


class TestPhaseResult:
    """Tests for PhaseResult dataclass."""

    def test_phase_result_success_with_data(self) -> None:
        """PhaseResult stores success state with data."""
        data = {"intentions": {"bob": "go to tavern"}}
        result = PhaseResult(success=True, data=data)

        assert result.success is True
        assert result.data == data
        assert result.error is None

    def test_phase_result_failure_with_error(self) -> None:
        """PhaseResult stores failure state with error message."""
        result = PhaseResult(success=False, data=None, error="LLM timeout")

        assert result.success is False
        assert result.data is None
        assert result.error == "LLM timeout"

    def test_phase_result_default_error_is_none(self) -> None:
        """PhaseResult.error defaults to None when not provided."""
        result = PhaseResult(success=True, data={})

        assert result.error is None

    def test_phase_result_data_accepts_any_type(self) -> None:
        """PhaseResult.data accepts any type."""
        # Dict
        result1 = PhaseResult(success=True, data={"key": "value"})
        assert result1.data == {"key": "value"}

        # List
        result2 = PhaseResult(success=True, data=[1, 2, 3])
        assert result2.data == [1, 2, 3]

        # None
        result3 = PhaseResult(success=True, data=None)
        assert result3.data is None

        # String with non-ASCII
        result4 = PhaseResult(success=True, data="Привет мир 你好")
        assert result4.data == "Привет мир 你好"

    def test_phase_result_equality(self) -> None:
        """Two PhaseResults with same values are equal."""
        result1 = PhaseResult(success=True, data={"x": 1}, error=None)
        result2 = PhaseResult(success=True, data={"x": 1}, error=None)

        assert result1 == result2

    def test_phase_result_inequality(self) -> None:
        """PhaseResults with different values are not equal."""
        result1 = PhaseResult(success=True, data={"x": 1})
        result2 = PhaseResult(success=False, data={"x": 1})

        assert result1 != result2

    def test_phase_result_success_with_empty_data(self) -> None:
        """PhaseResult can succeed with empty dict."""
        result = PhaseResult(success=True, data={})

        assert result.success is True
        assert result.data == {}

    def test_phase_result_failure_with_non_ascii_error(self) -> None:
        """PhaseResult error message can contain non-ASCII."""
        result = PhaseResult(success=False, data=None, error="Ошибка: не удалось подключиться")

        assert result.error == "Ошибка: не удалось подключиться"

    def test_phase_result_with_stats(self) -> None:
        """PhaseResult stores BatchStats correctly."""
        stats = BatchStats(
            total_tokens=1500,
            reasoning_tokens=500,
            cached_tokens=100,
            request_count=3,
            success_count=2,
            error_count=1,
            results=[
                RequestResult(
                    entity_key="intention:bob",
                    success=True,
                    usage=ResponseUsage(
                        input_tokens=100,
                        output_tokens=50,
                        total_tokens=150,
                    ),
                    reasoning_summary=["Thinking..."],
                ),
            ],
        )
        result = PhaseResult(success=True, data={"key": "value"}, stats=stats)

        assert result.stats is stats
        assert result.stats.total_tokens == 1500
        assert result.stats.reasoning_tokens == 500
        assert len(result.stats.results) == 1
        assert result.stats.results[0].entity_key == "intention:bob"

    def test_phase_result_stats_default_none(self) -> None:
        """PhaseResult.stats defaults to None."""
        result = PhaseResult(success=True, data={})

        assert result.stats is None

    def test_phase_result_stats_equality(self) -> None:
        """Two PhaseResults with same stats are equal."""
        stats = BatchStats(total_tokens=100)
        result1 = PhaseResult(success=True, data={}, stats=stats)
        result2 = PhaseResult(success=True, data={}, stats=stats)

        assert result1 == result2

    def test_phase_result_stats_with_failure(self) -> None:
        """PhaseResult can have stats even on failure."""
        stats = BatchStats(
            request_count=1,
            error_count=1,
            results=[
                RequestResult(
                    entity_key="intention:alice",
                    success=False,
                    error="Timeout",
                ),
            ],
        )
        result = PhaseResult(success=False, data=None, error="Phase failed", stats=stats)

        assert result.success is False
        assert result.stats is not None
        assert result.stats.error_count == 1
