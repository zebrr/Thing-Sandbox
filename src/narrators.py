"""Output handlers for Thing' Sandbox.

Narrators receive tick results and deliver narratives to various destinations:
console, files, Telegram, web.

Example:
    >>> from src.narrators import ConsoleNarrator
    >>> from src.runner import TickResult
    >>> narrator = ConsoleNarrator()
    >>> result = TickResult(
    ...     sim_id="my-sim",
    ...     tick_number=42,
    ...     narratives={"tavern": "Bob enters."},
    ...     location_names={"tavern": "The Rusty Tankard"},
    ...     success=True,
    ... )
    >>> narrator.output(result)
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.runner import TickResult

logger = logging.getLogger(__name__)

# Box drawing character for header/footer
BOX_CHAR = "═"
HEADER_WIDTH = 43


class Narrator(Protocol):
    """Interface that all narrators must implement.

    Example:
        >>> class MyNarrator:
        ...     def output(self, result: TickResult) -> None:
        ...         print(result.tick_number)
    """

    def output(self, result: TickResult) -> None:
        """Output tick result to destination.

        Args:
            result: TickResult from completed tick.
        """
        ...


class ConsoleNarrator:
    """Outputs narratives to stdout.

    Formats tick results with box-drawing characters and location headers.

    Example:
        >>> narrator = ConsoleNarrator()
        >>> narrator.output(result)  # Prints formatted output to console
    """

    def __init__(self, show_narratives: bool = True) -> None:
        """Initialize console narrator.

        Args:
            show_narratives: Whether to show narrative text for each location.
                If False, only header/footer with tick number is printed.
        """
        self._show_narratives = show_narratives

    def output(self, result: TickResult) -> None:
        """Print narratives to stdout.

        Output format:
        ```
        ═══════════════════════════════════════════
        TICK 42
        ═══════════════════════════════════════════

        --- Tavern ---
        Narrative text here...

        --- Forest ---
        [No narrative]

        ═══════════════════════════════════════════
        ```

        Args:
            result: TickResult with narratives and location names.
        """
        try:
            self._print_output(result)
        except Exception as e:
            logger.warning("ConsoleNarrator failed: %s", e)

    def _print_output(self, result: TickResult) -> None:
        """Internal method to print formatted output.

        Args:
            result: TickResult with narratives.
        """
        # Use UTF-8 encoding with error handling for Windows console
        try:
            # Try to reconfigure stdout for UTF-8 if possible
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass  # Ignore if reconfiguration fails

        header_line = BOX_CHAR * HEADER_WIDTH

        # Header
        self._safe_print("")
        self._safe_print(header_line)
        self._safe_print(f"{result.sim_id} - tick #{result.tick_number}")
        self._safe_print(header_line)
        self._safe_print("")

        # Narratives for each location (only if show_narratives is True)
        if self._show_narratives:
            for loc_id, narrative in result.narratives.items():
                loc_name = result.location_names.get(loc_id, loc_id)
                self._safe_print(f"----- {loc_name} ({loc_id}) -----")
                self._safe_print("")

                if narrative and narrative.strip():
                    self._safe_print(narrative)
                else:
                    self._safe_print("[No narrative]")

                self._safe_print("")

        # Footer
        self._safe_print(header_line)
        self._safe_print("")

    def _safe_print(self, text: str) -> None:
        """Print text with encoding error handling.

        Args:
            text: Text to print.
        """
        try:
            print(text)
        except UnicodeEncodeError:
            # Fallback: replace unencodable characters
            encoded = text.encode(sys.stdout.encoding or "utf-8", errors="replace")
            print(encoded.decode(sys.stdout.encoding or "utf-8", errors="replace"))
