"""LLM error hierarchy for Thing' Sandbox.

Defines unified exception types for all LLM-related errors.
Used by adapters and LLMClient to communicate error conditions.

Example:
    >>> from src.utils.llm_errors import LLMRefusalError
    >>> try:
    ...     raise LLMRefusalError("Content policy violation")
    ... except LLMRefusalError as e:
    ...     print(e.refusal_message)
    Content policy violation
"""


class LLMError(Exception):
    """Base class for LLM-related errors.

    All LLM exceptions inherit from this class, allowing callers
    to catch all LLM errors with a single except clause.

    Example:
        >>> raise LLMError("Generic LLM failure")
        Traceback (most recent call last):
        ...
        LLMError: Generic LLM failure
    """

    pass


class LLMRefusalError(LLMError):
    """Model refused request due to safety policy.

    Raised when the model returns a refusal response instead of
    completing the request. Contains the refusal explanation.

    Example:
        >>> e = LLMRefusalError("I cannot assist with that request")
        >>> e.refusal_message
        'I cannot assist with that request'
    """

    def __init__(self, refusal_message: str) -> None:
        """Initialize refusal error.

        Args:
            refusal_message: Explanation from model about why it refused.
        """
        self.refusal_message = refusal_message
        super().__init__(f"Model refused: {refusal_message}")


class LLMIncompleteError(LLMError):
    """Response truncated due to token limit.

    Raised when the model's response is cut off because it reached
    max_output_tokens limit before completing the structured output.

    Example:
        >>> e = LLMIncompleteError("max_output_tokens")
        >>> e.reason
        'max_output_tokens'
    """

    def __init__(self, reason: str) -> None:
        """Initialize incomplete error.

        Args:
            reason: Truncation reason from API (e.g., "max_output_tokens").
        """
        self.reason = reason
        super().__init__(f"Response incomplete: {reason}")


class LLMRateLimitError(LLMError):
    """Rate limit exceeded after all retries.

    Raised when the API returns 429 Too Many Requests and all
    retry attempts have been exhausted.

    Example:
        >>> raise LLMRateLimitError("Rate limit after 4 attempts")
        Traceback (most recent call last):
        ...
        LLMRateLimitError: Rate limit after 4 attempts
    """

    def __init__(self, message: str) -> None:
        """Initialize rate limit error.

        Args:
            message: Description of rate limit condition.
        """
        super().__init__(message)


class LLMTimeoutError(LLMError):
    """Request timeout after all retries.

    Raised when the request times out and all retry attempts
    have been exhausted.

    Example:
        >>> raise LLMTimeoutError("Timeout after 4 attempts")
        Traceback (most recent call last):
        ...
        LLMTimeoutError: Timeout after 4 attempts
    """

    def __init__(self, message: str) -> None:
        """Initialize timeout error.

        Args:
            message: Description of timeout condition.
        """
        super().__init__(message)
