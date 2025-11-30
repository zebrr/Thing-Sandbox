"""Standard exit codes for CLI.

Provides consistent error handling through a unified code system
with support for readable names and logging.

Example:
    >>> from src.utils.exit_codes import EXIT_SUCCESS, log_exit
    >>> import logging
    >>> logger = logging.getLogger(__name__)
    >>> log_exit(logger, EXIT_SUCCESS, "Tick completed")
"""

import logging

# Exit code constants
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_RUNTIME_ERROR = 3
EXIT_API_LIMIT_ERROR = 4
EXIT_IO_ERROR = 5

# Mapping: code -> name
EXIT_CODE_NAMES: dict[int, str] = {
    EXIT_SUCCESS: "SUCCESS",
    EXIT_CONFIG_ERROR: "CONFIG_ERROR",
    EXIT_INPUT_ERROR: "INPUT_ERROR",
    EXIT_RUNTIME_ERROR: "RUNTIME_ERROR",
    EXIT_API_LIMIT_ERROR: "API_LIMIT_ERROR",
    EXIT_IO_ERROR: "IO_ERROR",
}

# Mapping: code -> description
EXIT_CODE_DESCRIPTIONS: dict[int, str] = {
    EXIT_SUCCESS: "Successful execution",
    EXIT_CONFIG_ERROR: "Configuration error (missing API key, broken config.toml)",
    EXIT_INPUT_ERROR: "Input data error (broken JSON, invalid schemas)",
    EXIT_RUNTIME_ERROR: "Runtime error (LLM failures after retries, unexpected exceptions)",
    EXIT_API_LIMIT_ERROR: "API rate limit exceeded (OpenAI TPM/RPM limits)",
    EXIT_IO_ERROR: "File system error (cannot write to simulations/)",
}


def get_exit_code_name(code: int) -> str:
    """Return readable name for exit code.

    Args:
        code: Exit code integer.

    Returns:
        Code name (e.g. "CONFIG_ERROR") or "UNKNOWN({code})" for unknown codes.
    """
    return EXIT_CODE_NAMES.get(code, f"UNKNOWN({code})")


def get_exit_code_description(code: int) -> str:
    """Return description for exit code.

    Args:
        code: Exit code integer.

    Returns:
        Code description or "Unknown exit code: {code}" for unknown codes.
    """
    return EXIT_CODE_DESCRIPTIONS.get(code, f"Unknown exit code: {code}")


def log_exit(logger: logging.Logger, code: int, message: str | None = None) -> None:
    """Log exit code with optional message.

    Args:
        logger: Logger object.
        code: Exit code.
        message: Additional context (optional).

    Note:
        SUCCESS is logged via logger.info(), all other codes via logger.error().
    """
    code_name = get_exit_code_name(code)
    code_description = get_exit_code_description(code)

    if message:
        log_message = f"[{code_name}] {code_description}: {message}"
    else:
        log_message = f"[{code_name}] {code_description}"

    if code == EXIT_SUCCESS:
        logger.info(log_message)
    else:
        logger.error(log_message)
