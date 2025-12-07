"""Common types for phase modules.

Example:
    >>> from src.phases.common import PhaseResult
    >>> result = PhaseResult(success=True, data={"key": "value"})
    >>> result.success
    True
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class PhaseResult:
    """Result of phase execution.

    Attributes:
        success: Whether the phase completed successfully.
        data: Phase-specific output data.
        error: Error message if success is False.

    Example:
        >>> result = PhaseResult(success=True, data={"intentions": {}})
        >>> result.error is None
        True
    """

    success: bool
    data: Any
    error: str | None = None
