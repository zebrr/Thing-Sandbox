"""Unit tests for phases/common module."""

from src.phases.common import PhaseResult


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
