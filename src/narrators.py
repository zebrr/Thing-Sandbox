"""Output handlers for Thing' Sandbox.

Narrators receive tick reports and deliver narratives to various destinations:
console, files, Telegram, web.

Example:
    >>> from datetime import datetime
    >>> from src.narrators import ConsoleNarrator
    >>> from src.runner import TickReport
    >>> narrator = ConsoleNarrator()
    >>> report = TickReport(
    ...     sim_id="my-sim",
    ...     tick_number=42,
    ...     narratives={"tavern": "Bob enters."},
    ...     location_names={"tavern": "The Rusty Tankard"},
    ...     success=True,
    ...     timestamp=datetime.now(),
    ...     duration=8.2,
    ...     phases={},
    ...     simulation=sim,
    ...     pending_memories={},
    ... )
    >>> narrator.output(report)
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.runner import PhaseData, TickReport
    from src.utils.storage import Simulation

logger = logging.getLogger(__name__)

# Box drawing character for header/footer
BOX_CHAR = "═"
HEADER_WIDTH = 43


class Narrator(Protocol):
    """Interface that all narrators must implement.

    Example:
        >>> class MyNarrator:
        ...     def output(self, report: TickReport) -> None:
        ...         print(report.tick_number)
        ...     async def on_tick_start(self, sim_id, tick_number, simulation) -> None:
        ...         pass
        ...     async def on_phase_complete(self, phase_name, phase_data) -> None:
        ...         pass
    """

    def output(self, report: TickReport) -> None:
        """Output tick report to destination.

        Args:
            report: TickReport from completed tick.
        """
        ...

    async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
        """Called when tick execution begins.

        Awaited directly by runner (fast, no network I/O expected).

        Args:
            sim_id: Simulation identifier.
            tick_number: Tick number about to execute (current_tick + 1).
            simulation: Simulation instance with characters and locations.
        """
        ...

    async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """Called after each phase completes successfully.

        Uses fire-and-forget pattern: runner creates tasks but doesn't await
        immediately. All tasks are awaited at end of tick with timeout.

        Args:
            phase_name: Name of completed phase (phase1, phase2a, phase2b, phase3, phase4).
            phase_data: Phase execution data including duration, stats, and output.
        """
        ...


class ConsoleNarrator:
    """Outputs narratives to stdout.

    Formats tick reports with box-drawing characters and location headers.

    Example:
        >>> narrator = ConsoleNarrator()
        >>> narrator.output(report)  # Prints formatted output to console
    """

    def __init__(self, show_narratives: bool = True) -> None:
        """Initialize console narrator.

        Args:
            show_narratives: Whether to show narrative text for each location.
                If False, only header/footer with tick number is printed.
        """
        self._show_narratives = show_narratives

    def output(self, report: TickReport) -> None:
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
            report: TickReport with narratives and location names.
        """
        try:
            self._print_output(report)
        except Exception as e:
            logger.warning("ConsoleNarrator failed: %s", e)

    def _print_output(self, report: TickReport) -> None:
        """Internal method to print formatted output.

        Args:
            report: TickReport with narratives.
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
        self._safe_print(f"{report.sim_id} - tick #{report.tick_number}")
        self._safe_print(header_line)
        self._safe_print("")

        # Narratives for each location (only if show_narratives is True)
        if self._show_narratives:
            for loc_id, narrative in report.narratives.items():
                loc_name = report.location_names.get(loc_id, loc_id)
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

    async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
        """No-op implementation for tick start event.

        Args:
            sim_id: Simulation identifier.
            tick_number: Tick number about to execute.
            simulation: Simulation instance (ignored).
        """
        pass

    async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """No-op implementation for phase complete event.

        Args:
            phase_name: Name of completed phase.
            phase_data: Phase execution data.
        """
        pass
