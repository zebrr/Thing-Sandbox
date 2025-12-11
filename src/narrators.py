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
from typing import TYPE_CHECKING, Any, Protocol

from src.utils.llm import BatchStats
from src.utils.telegram_client import TelegramClient

if TYPE_CHECKING:
    from src.runner import PhaseData, TickReport
    from src.utils.storage import Simulation

__all__ = ["Narrator", "ConsoleNarrator", "TelegramNarrator", "escape_html"]

logger = logging.getLogger(__name__)

# Box drawing character for header/footer
BOX_CHAR = "═"
HEADER_WIDTH = 43


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram.

    Escapes: & < >

    Args:
        text: Raw text that may contain HTML special characters.

    Returns:
        Text safe for Telegram HTML parse mode.

    Example:
        >>> escape_html("<b>Hello & World</b>")
        '&lt;b&gt;Hello &amp; World&lt;/b&gt;'
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
        # Skip all output if narratives are disabled
        if not self._show_narratives:
            return

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


class TelegramNarrator:
    """Sends tick updates to Telegram channel via lifecycle methods.

    Implements Narrator protocol. Uses async on_phase_complete to send
    intentions after Phase 1 and narratives after Phase 2b.

    Runner uses fire-and-forget pattern: creates tasks for on_phase_complete
    but doesn't await immediately. All tasks awaited at end of tick.

    Example:
        >>> from src.utils.telegram_client import TelegramClient
        >>> client = TelegramClient("123456:ABC-token")
        >>> narrator = TelegramNarrator(
        ...     client=client,
        ...     chat_id="-1001234567890",
        ...     mode="full_stats",
        ...     group_intentions=True,
        ...     group_narratives=True,
        ... )
    """

    def __init__(
        self,
        client: TelegramClient,
        chat_id: str,
        mode: str,
        group_intentions: bool,
        group_narratives: bool,
        message_thread_id: int | None = None,
    ) -> None:
        """Initialize Telegram narrator.

        Args:
            client: TelegramClient instance (from utils.telegram_client).
            chat_id: Target chat/channel ID.
            mode: Output mode (narratives, narratives_stats, full, full_stats).
            group_intentions: Group all intentions in one message.
            group_narratives: Group all narratives in one message.
            message_thread_id: Forum topic ID for supergroups with topics enabled.
        """
        self._client = client
        self._chat_id = chat_id
        self._mode = mode
        self._group_intentions = group_intentions
        self._group_narratives = group_narratives
        self._message_thread_id = message_thread_id

        # Set by on_tick_start, used in on_phase_complete
        self._simulation: Simulation | None = None
        self._sim_id: str = ""
        self._tick_number: int = 0

        # Accumulate stats for phase2 (2a + 2b)
        self._phase2a_stats: BatchStats | None = None
        self._phase2a_duration: float = 0.0

    async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
        """Store simulation reference for name lookups.

        Args:
            sim_id: Simulation identifier.
            tick_number: Tick number about to execute.
            simulation: Simulation instance with characters and locations.
        """
        self._simulation = simulation
        self._sim_id = sim_id
        self._tick_number = tick_number
        self._phase2a_stats = None
        self._phase2a_duration = 0.0

    async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """Send messages after relevant phases.

        Args:
            phase_name: Name of completed phase.
            phase_data: Phase execution data.
        """
        if phase_name == "phase1" and self._mode in ("full", "full_stats"):
            await self._send_intentions(phase_data)
        elif phase_name == "phase2a":
            # Store for combined stats with phase2b
            self._phase2a_stats = phase_data.stats
            self._phase2a_duration = phase_data.duration
        elif phase_name == "phase2b":
            await self._send_narratives(phase_data)

    def output(self, report: TickReport) -> None:
        """No-op — all messages sent in on_phase_complete.

        Args:
            report: TickReport (ignored).
        """
        pass

    async def _send_intentions(self, phase_data: PhaseData) -> None:
        """Format and send intentions to Telegram.

        Args:
            phase_data: Phase 1 execution data with intentions.
        """
        if self._simulation is None:
            logger.warning("TelegramNarrator: simulation is None, skipping intentions")
            return

        intentions = phase_data.data  # dict[str, IntentionResponse]
        if not intentions:
            return

        show_stats = self._mode.endswith("_stats")
        stats_footer = ""
        if show_stats and phase_data.stats:
            stats_footer = self._format_stats_footer(
                phase_num=1,
                total_tokens=phase_data.stats.total_tokens,
                reasoning_tokens=phase_data.stats.reasoning_tokens,
                duration=phase_data.duration,
            )

        if self._group_intentions:
            # Single grouped message
            await self._send_intentions_grouped(intentions, stats_footer)
        else:
            # Multiple per-character messages
            await self._send_intentions_per_character(intentions, stats_footer)

    async def _send_intentions_grouped(
        self,
        intentions: dict[str, Any],
        stats_footer: str,
    ) -> None:
        """Send all intentions as single grouped message.

        Args:
            intentions: dict[str, IntentionResponse] from phase1.
            stats_footer: Stats footer to append (empty if stats disabled).
        """
        assert self._simulation is not None

        lines = [f"🎯 <b>{escape_html(self._sim_id)} — tick #{self._tick_number} | Intentions</b>"]

        for char_id, response in intentions.items():
            char = self._simulation.characters.get(char_id)
            char_name = char.identity.name if char else char_id
            intention_text = escape_html(response.intention)
            lines.append(f"\n<b>{escape_html(char_name)}:</b>\n{intention_text}")

        if stats_footer:
            lines.append(stats_footer)

        message = "\n".join(lines)
        try:
            success = await self._client.send_message(
                self._chat_id, message, message_thread_id=self._message_thread_id
            )
            if success:
                logger.info("Sent %d intentions", len(intentions))
            else:
                logger.warning("Failed to send grouped intentions")
        except Exception as e:
            logger.warning("Failed to send grouped intentions: %s", e)

    async def _send_intentions_per_character(
        self,
        intentions: dict[str, Any],
        stats_footer: str,
    ) -> None:
        """Send intentions as separate per-character messages.

        Args:
            intentions: dict[str, IntentionResponse] from phase1.
            stats_footer: Stats footer to append to last message.
        """
        assert self._simulation is not None

        items = list(intentions.items())
        total = len(items)
        sent_count = 0

        for i, (char_id, response) in enumerate(items):
            char = self._simulation.characters.get(char_id)
            char_name = char.identity.name if char else char_id
            intention_text = escape_html(response.intention)

            header = (
                f"🎯 <b>{escape_html(self._sim_id)} — tick #{self._tick_number} | "
                f"{escape_html(char_name)}</b>"
            )
            message = f"{header}\n\n{intention_text}"

            # Add stats footer only to last message
            if i == total - 1 and stats_footer:
                message += stats_footer

            try:
                success = await self._client.send_message(
                    self._chat_id, message, message_thread_id=self._message_thread_id
                )
                if success:
                    sent_count += 1
                else:
                    logger.warning("Failed to send intention for %s", char_id)
            except Exception as e:
                logger.warning("Failed to send intention for %s: %s", char_id, e)

        if sent_count > 0:
            logger.info("Sent %d intentions", sent_count)

    async def _send_narratives(self, phase_data: PhaseData) -> None:
        """Format and send narratives to Telegram.

        Args:
            phase_data: Phase 2b execution data with narratives.
        """
        if self._simulation is None:
            logger.warning("TelegramNarrator: simulation is None, skipping narratives")
            return

        narratives = phase_data.data  # dict[str, NarrativeResponse]
        if not narratives:
            return

        show_stats = self._mode.endswith("_stats")
        stats_footer = ""
        if show_stats and phase_data.stats:
            # Combined stats from phase2a + phase2b
            total_tokens = phase_data.stats.total_tokens
            reasoning_tokens = phase_data.stats.reasoning_tokens
            duration = phase_data.duration

            if self._phase2a_stats:
                total_tokens += self._phase2a_stats.total_tokens
                reasoning_tokens += self._phase2a_stats.reasoning_tokens
                duration += self._phase2a_duration

            stats_footer = self._format_stats_footer(
                phase_num=2,
                total_tokens=total_tokens,
                reasoning_tokens=reasoning_tokens,
                duration=duration,
            )

        if self._group_narratives:
            # Single grouped message
            await self._send_narratives_grouped(narratives, stats_footer)
        else:
            # Multiple per-location messages
            await self._send_narratives_per_location(narratives, stats_footer)

    async def _send_narratives_grouped(
        self,
        narratives: dict[str, Any],
        stats_footer: str,
    ) -> None:
        """Send all narratives as single grouped message.

        Args:
            narratives: dict[str, NarrativeResponse] from phase2b.
            stats_footer: Stats footer to append (empty if stats disabled).
        """
        assert self._simulation is not None

        lines = [f"📖 <b>{escape_html(self._sim_id)} — tick #{self._tick_number} | Narratives</b>"]

        for loc_id, response in narratives.items():
            loc = self._simulation.locations.get(loc_id)
            loc_name = loc.identity.name if loc else loc_id
            narrative_text = escape_html(response.narrative)
            lines.append(f"\n<b>{escape_html(loc_name)}</b>\n\n{narrative_text}")

        if stats_footer:
            lines.append(stats_footer)

        message = "\n".join(lines)
        try:
            success = await self._client.send_message(
                self._chat_id, message, message_thread_id=self._message_thread_id
            )
            if success:
                logger.info("Sent %d narratives", len(narratives))
            else:
                logger.warning("Failed to send grouped narratives")
        except Exception as e:
            logger.warning("Failed to send grouped narratives: %s", e)

    async def _send_narratives_per_location(
        self,
        narratives: dict[str, Any],
        stats_footer: str,
    ) -> None:
        """Send narratives as separate per-location messages.

        Args:
            narratives: dict[str, NarrativeResponse] from phase2b.
            stats_footer: Stats footer to append to last message.
        """
        assert self._simulation is not None

        items = list(narratives.items())
        total = len(items)
        sent_count = 0

        for i, (loc_id, response) in enumerate(items):
            loc = self._simulation.locations.get(loc_id)
            loc_name = loc.identity.name if loc else loc_id
            narrative_text = escape_html(response.narrative)

            header = (
                f"📖 <b>{escape_html(self._sim_id)} — tick #{self._tick_number} | "
                f"{escape_html(loc_name)}</b>"
            )
            message = f"{header}\n\n{narrative_text}"

            # Add stats footer only to last message
            if i == total - 1 and stats_footer:
                message += stats_footer

            try:
                success = await self._client.send_message(
                    self._chat_id, message, message_thread_id=self._message_thread_id
                )
                if success:
                    sent_count += 1
                else:
                    logger.warning("Failed to send narrative for %s", loc_id)
            except Exception as e:
                logger.warning("Failed to send narrative for %s: %s", loc_id, e)

        if sent_count > 0:
            logger.info("Sent %d narratives", sent_count)

    def _format_stats_footer(
        self,
        phase_num: int,
        total_tokens: int,
        reasoning_tokens: int,
        duration: float,
    ) -> str:
        """Format stats footer for messages.

        Args:
            phase_num: Phase number (1 or 2).
            total_tokens: Total tokens used.
            reasoning_tokens: Reasoning tokens used.
            duration: Duration in seconds.

        Returns:
            Formatted stats footer string.
        """
        return (
            f"\n───\n"
            f"📊 <i>Phase {phase_num}: {total_tokens:,} tok · "
            f"{reasoning_tokens:,} reason · {duration:.1f}s</i>"
        )
