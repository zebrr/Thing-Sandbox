"""Unit tests for exit_codes module."""

import logging
from unittest.mock import MagicMock

from src.utils.exit_codes import (
    EXIT_API_LIMIT_ERROR,
    EXIT_CODE_DESCRIPTIONS,
    EXIT_CODE_NAMES,
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_IO_ERROR,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    get_exit_code_description,
    get_exit_code_name,
    log_exit,
)


class TestExitCodeConstants:
    """Tests for exit code constant values."""

    def test_exit_success_is_zero(self) -> None:
        assert EXIT_SUCCESS == 0

    def test_exit_config_error_is_one(self) -> None:
        assert EXIT_CONFIG_ERROR == 1

    def test_exit_input_error_is_two(self) -> None:
        assert EXIT_INPUT_ERROR == 2

    def test_exit_runtime_error_is_three(self) -> None:
        assert EXIT_RUNTIME_ERROR == 3

    def test_exit_api_limit_error_is_four(self) -> None:
        assert EXIT_API_LIMIT_ERROR == 4

    def test_exit_io_error_is_five(self) -> None:
        assert EXIT_IO_ERROR == 5


class TestExitCodeDictionaries:
    """Tests for exit code dictionaries."""

    def test_all_codes_have_names(self) -> None:
        codes = [
            EXIT_SUCCESS,
            EXIT_CONFIG_ERROR,
            EXIT_INPUT_ERROR,
            EXIT_RUNTIME_ERROR,
            EXIT_API_LIMIT_ERROR,
            EXIT_IO_ERROR,
        ]
        for code in codes:
            assert code in EXIT_CODE_NAMES

    def test_all_codes_have_descriptions(self) -> None:
        codes = [
            EXIT_SUCCESS,
            EXIT_CONFIG_ERROR,
            EXIT_INPUT_ERROR,
            EXIT_RUNTIME_ERROR,
            EXIT_API_LIMIT_ERROR,
            EXIT_IO_ERROR,
        ]
        for code in codes:
            assert code in EXIT_CODE_DESCRIPTIONS


class TestGetExitCodeName:
    """Tests for get_exit_code_name function."""

    def test_returns_success_for_zero(self) -> None:
        assert get_exit_code_name(0) == "SUCCESS"

    def test_returns_config_error_for_one(self) -> None:
        assert get_exit_code_name(1) == "CONFIG_ERROR"

    def test_returns_input_error_for_two(self) -> None:
        assert get_exit_code_name(2) == "INPUT_ERROR"

    def test_returns_runtime_error_for_three(self) -> None:
        assert get_exit_code_name(3) == "RUNTIME_ERROR"

    def test_returns_api_limit_error_for_four(self) -> None:
        assert get_exit_code_name(4) == "API_LIMIT_ERROR"

    def test_returns_io_error_for_five(self) -> None:
        assert get_exit_code_name(5) == "IO_ERROR"

    def test_returns_unknown_for_unknown_code(self) -> None:
        assert get_exit_code_name(99) == "UNKNOWN(99)"

    def test_returns_unknown_for_negative_code(self) -> None:
        assert get_exit_code_name(-1) == "UNKNOWN(-1)"


class TestGetExitCodeDescription:
    """Tests for get_exit_code_description function."""

    def test_returns_description_for_success(self) -> None:
        description = get_exit_code_description(EXIT_SUCCESS)
        assert "Successful" in description

    def test_returns_description_for_config_error(self) -> None:
        description = get_exit_code_description(EXIT_CONFIG_ERROR)
        assert "config" in description.lower()

    def test_returns_description_for_input_error(self) -> None:
        description = get_exit_code_description(EXIT_INPUT_ERROR)
        assert "Input" in description

    def test_returns_description_for_runtime_error(self) -> None:
        description = get_exit_code_description(EXIT_RUNTIME_ERROR)
        assert "Runtime" in description

    def test_returns_description_for_api_limit_error(self) -> None:
        description = get_exit_code_description(EXIT_API_LIMIT_ERROR)
        assert "API" in description or "rate" in description.lower()

    def test_returns_description_for_io_error(self) -> None:
        description = get_exit_code_description(EXIT_IO_ERROR)
        assert "File" in description or "system" in description.lower()

    def test_returns_unknown_description_for_unknown_code(self) -> None:
        description = get_exit_code_description(99)
        assert description == "Unknown exit code: 99"

    def test_returns_unknown_description_for_negative_code(self) -> None:
        description = get_exit_code_description(-42)
        assert description == "Unknown exit code: -42"


class TestLogExit:
    """Tests for log_exit function."""

    def test_success_logs_via_info(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_SUCCESS)
        logger.info.assert_called_once()
        logger.error.assert_not_called()

    def test_config_error_logs_via_error(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_CONFIG_ERROR)
        logger.error.assert_called_once()
        logger.info.assert_not_called()

    def test_input_error_logs_via_error(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_INPUT_ERROR)
        logger.error.assert_called_once()

    def test_runtime_error_logs_via_error(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_RUNTIME_ERROR)
        logger.error.assert_called_once()

    def test_api_limit_error_logs_via_error(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_API_LIMIT_ERROR)
        logger.error.assert_called_once()

    def test_io_error_logs_via_error(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_IO_ERROR)
        logger.error.assert_called_once()

    def test_log_message_includes_code_name(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_CONFIG_ERROR)
        call_args = logger.error.call_args[0][0]
        assert "CONFIG_ERROR" in call_args

    def test_log_message_includes_description(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_SUCCESS)
        call_args = logger.info.call_args[0][0]
        assert "Successful" in call_args

    def test_log_message_includes_custom_message(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        custom_msg = "Тест с кириллицей: симуляция завершена"
        log_exit(logger, EXIT_SUCCESS, custom_msg)
        call_args = logger.info.call_args[0][0]
        assert custom_msg in call_args

    def test_log_message_without_custom_message(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, EXIT_SUCCESS)
        call_args = logger.info.call_args[0][0]
        assert "[SUCCESS]" in call_args
        assert "Successful" in call_args

    def test_unknown_code_logs_via_error(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_exit(logger, 99)
        logger.error.assert_called_once()
        call_args = logger.error.call_args[0][0]
        assert "UNKNOWN(99)" in call_args
