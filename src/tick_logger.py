"""Tick logger for Thing' Sandbox.

Writes detailed tick logs to markdown files with full phase-by-phase
information including token usage, reasoning summaries, and entity state changes.

Example:
    >>> from pathlib import Path
    >>> from src.runner import PhaseData, TickReport
    >>> from src.tick_logger import TickLogger
    >>> logger = TickLogger(Path("simulations/my-sim"))
    >>> logger.write(report)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.runner import PhaseData, TickReport

if TYPE_CHECKING:
    from src.utils.llm import BatchStats

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["PhaseData", "TickLogger", "TickReport"]


class TickLogger:
    """Writes tick logs to markdown files.

    Creates detailed log files in simulations/{sim_id}/logs/ with full
    phase-by-phase information.

    Example:
        >>> logger = TickLogger(Path("simulations/my-sim"))
        >>> logger.write(report)
    """

    def __init__(self, sim_path: Path) -> None:
        """Initialize logger for a simulation.

        Args:
            sim_path: Path to simulation folder.
        """
        self._sim_path = sim_path

    def write(self, report: TickReport) -> None:
        """Write tick report to markdown file.

        Creates logs/ directory if needed and writes tick_NNNNNN.md file.

        Args:
            report: TickReport with tick data.

        Raises:
            StorageIOError: If file write fails.
        """
        # Ensure logs directory exists
        logs_dir = self._sim_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Build filename with padded tick number
        filename = f"tick_{report.tick_number:06d}.md"
        file_path = logs_dir / filename

        # Build content
        content = self._format_report(report)

        # Write file
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.debug("Wrote tick log: %s", file_path)
        except OSError as e:
            from src.utils.storage import StorageIOError

            raise StorageIOError(f"Failed to write tick log: {e}", file_path, e) from e

    def _format_report(self, report: TickReport) -> str:
        """Format complete tick report as markdown.

        Args:
            report: TickReport with tick data.

        Returns:
            Complete markdown content.
        """
        sections = [
            self._format_header(report),
            self._format_phase1(report),
            self._format_phase2a(report),
            self._format_phase2b(report),
            self._format_phase3(report),
            self._format_phase4(report),
        ]
        return "\n".join(sections)

    def _format_header(self, report: TickReport) -> str:
        """Format document header with simulation info and summary table.

        Args:
            report: TickReport with tick data.

        Returns:
            Header markdown section.
        """
        # Calculate totals from all phases
        total_tokens = 0
        reasoning_tokens = 0
        cached_tokens = 0
        request_count = 0

        for phase_data in report.phases.values():
            if phase_data.stats:
                total_tokens += phase_data.stats.total_tokens
                reasoning_tokens += phase_data.stats.reasoning_tokens
                cached_tokens += phase_data.stats.cached_tokens
                request_count += phase_data.stats.request_count

        timestamp_str = report.timestamp.strftime("%Y-%m-%d %H:%M")

        lines = [
            f"# Tick {report.tick_number}",
            "",
            f"**Simulation:** {report.sim_id}  ",
            f"**Timestamp:** {timestamp_str}  ",
            f"**Duration:** {report.duration:.1f}s",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total tokens | {total_tokens:,} |",
            f"| Reasoning tokens | {reasoning_tokens:,} |",
            f"| Cached tokens | {cached_tokens:,} |",
            f"| LLM requests | {request_count} |",
            "",
        ]
        return "\n".join(lines)

    def _format_phase1(self, report: TickReport) -> str:
        """Format Phase 1 section (character intentions).

        Args:
            report: TickReport with tick data.

        Returns:
            Phase 1 markdown section.
        """
        phase_data = report.phases.get("phase1")
        if not phase_data:
            return "## Phase 1: Intentions\n\n*(no data)*\n"

        stats = phase_data.stats
        tokens_str = self._format_tokens(stats)

        lines = [
            "## Phase 1: Intentions",
            "",
            f"**Duration:** {phase_data.duration:.1f}s | {tokens_str}",
            "",
        ]

        # Per-character subsections
        intentions = phase_data.data or {}
        for char_id, char in report.simulation.characters.items():
            lines.append(f"### {char.identity.name}")

            intention_resp = intentions.get(char_id)
            if intention_resp:
                lines.append(f"\n- **Intention:** {intention_resp.intention}")
            else:
                lines.append("\n- **Intention:** (none)")

            # Get reasoning from stats
            reasoning = self._get_reasoning_for_entity(stats, char_id, "intention")
            if reasoning:
                lines.append(f"\n- **Reasoning:** {reasoning}")

            lines.append("")

        return "\n".join(lines)

    def _format_phase2a(self, report: TickReport) -> str:
        """Format Phase 2a section (arbitration).

        Args:
            report: TickReport with tick data.

        Returns:
            Phase 2a markdown section.
        """
        phase_data = report.phases.get("phase2a")
        if not phase_data:
            return "## Phase 2a: Arbitration\n\n(no data)\n"

        stats = phase_data.stats
        tokens_str = self._format_tokens(stats)

        lines = [
            "## Phase 2a: Arbitration",
            "",
            f"**Duration:** {phase_data.duration:.1f}s | {tokens_str}",
            "",
        ]

        # Per-location subsections (including empty locations)
        master_results = phase_data.data or {}
        for loc_id, location in report.simulation.locations.items():
            lines.append(f"### {location.identity.name}")
            lines.append("")

            master_output = master_results.get(loc_id)

            # Characters section
            lines.append("**Characters:**")
            if master_output and master_output.characters:
                # Handle both list (real) and dict (mocked) characters
                chars = master_output.characters
                if isinstance(chars, dict):
                    chars = list(chars.values())
                for char_update in chars:
                    # Safe attribute access for mocked objects
                    state = getattr(char_update, "internal_state", None) or ""
                    intent = getattr(char_update, "external_intent", None) or ""
                    char_id = getattr(char_update, "character_id", "unknown")
                    char_loc = getattr(char_update, "location", "unknown")
                    memory = getattr(char_update, "memory_entry", None) or ""
                    lines.append(f"\n- **{char_id}:**")
                    lines.append(f'\n  target location={char_loc}')
                    lines.append(f'\n  updated state="{state}"')
                    lines.append(f'\n  updated intent="{intent}"')
                    lines.append(f'\n  new memory="{memory}"')
            else:
                lines.append("(none)")
            lines.append("")

            # Location update section
            lines.append("\n**Location:**")
            if master_output and master_output.location:
                loc_update = master_output.location
                moment = getattr(loc_update, "moment", None)
                description = getattr(loc_update, "description", None)
                moment_str = f'"{moment}"' if moment else "unchanged"
                desc_str = f'"{description}"' if description else "unchanged"
                lines.append(f'\n  current moment={moment_str}')
                lines.append(f'\n  description={desc_str}')
            else:
                lines.append("\n  moment=unchanged")
                lines.append("\n  description=unchanged")
            lines.append("")

            # Reasoning
            reasoning = self._get_reasoning_for_entity(stats, loc_id, "resolution")
            if reasoning:
                lines.append(f"**Reasoning:** {reasoning}")
                lines.append("")

        return "\n".join(lines)

    def _format_phase2b(self, report: TickReport) -> str:
        """Format Phase 2b section (narratives).

        Args:
            report: TickReport with tick data.

        Returns:
            Phase 2b markdown section.
        """
        phase_data = report.phases.get("phase2b")
        if not phase_data:
            return "## Phase 2b: Narratives\n\n*(no data)*\n"

        stats = phase_data.stats
        tokens_str = self._format_tokens(stats)

        lines = [
            "## Phase 2b: Narratives",
            "",
            f"**Duration:** {phase_data.duration:.1f}s | {tokens_str}",
            "",
        ]

        # Per-location subsections
        for loc_id, location in report.simulation.locations.items():
            lines.append(f"### {location.identity.name}")
            lines.append("")

            narrative = report.narratives.get(loc_id, "")
            if narrative and narrative.strip():
                # Format as blockquote, handling multiline
                for para in narrative.split("\n\n"):
                    lines.append(f"{para.strip()}")
                    lines.append("")
            else:
                lines.append("(no narrative)")

        return "\n".join(lines)

    def _format_phase3(self, report: TickReport) -> str:
        """Format Phase 3 section (state application).

        Args:
            report: TickReport with tick data.

        Returns:
            Phase 3 markdown section.
        """
        phase_data = report.phases.get("phase3")
        if not phase_data:
            return "## Phase 3: State Application\n\n(no data)\n"

        char_count = len(report.simulation.characters)
        loc_count = len(report.simulation.locations)

        lines = [
            "## Phase 3: State Application",
            "",
            f"**Duration:** {phase_data.duration:.2f}s | *(no LLM)* — "
            f"Applied {char_count} character updates, {loc_count} location updates",
            "",
        ]

        return "\n".join(lines)

    def _format_phase4(self, report: TickReport) -> str:
        """Format Phase 4 section (memory update).

        Args:
            report: TickReport with tick data.

        Returns:
            Phase 4 markdown section.
        """
        phase_data = report.phases.get("phase4")
        if not phase_data:
            return "## Phase 4: Memory\n\n*(no data)*\n"

        stats = phase_data.stats
        tokens_str = self._format_tokens(stats)

        # Get max cells from simulation config (default 5)
        max_cells = 5

        lines = [
            "## Phase 4: Memory",
            "",
            f"**Duration:** {phase_data.duration:.1f}s | {tokens_str}",
            "",
        ]

        # Per-character subsections
        for char_id, char in report.simulation.characters.items():
            lines.append(f"### {char.identity.name}")

            # New memory from pending_memories
            new_memory = report.pending_memories.get(char_id)
            if new_memory:
                lines.append(f'\n- **New memory:** "{new_memory}"')
            else:
                lines.append("\n- **New memory:** (none)")

            # Cells count
            cells_count = len(char.memory.cells)

            # Check if summarization occurred based on reasoning_tokens > 0
            # Note: reasoning_summary may be empty even when reasoning occurred
            had_reasoning = self._had_reasoning_for_entity(stats, char_id, "memory")
            reasoning_text = self._get_reasoning_for_entity(stats, char_id, "memory")

            if had_reasoning:
                lines.append(f"- **Cells:** {cells_count}/{max_cells} (summarized)")
                if reasoning_text:
                    lines.append(f"- **Reasoning:** {reasoning_text}")
            else:
                lines.append(f"- **Cells:** {cells_count}/{max_cells} (no summarization)")

            lines.append("")

        return "\n".join(lines)

    def _format_tokens(self, stats: BatchStats | None) -> str:
        """Format token statistics string.

        Args:
            stats: BatchStats or None.

        Returns:
            Formatted string like "**Tokens:** 1,200 (reasoning: 400)".
        """
        if not stats:
            return "*(no LLM)*"

        return f"**Tokens:** {stats.total_tokens:,} (reasoning: {stats.reasoning_tokens:,})"

    def _get_reasoning_for_entity(
        self, stats: BatchStats | None, entity_id: str, chain_type: str
    ) -> str | None:
        """Extract reasoning summary for specific entity from BatchStats.

        Args:
            stats: BatchStats with results.
            entity_id: Entity identifier (e.g., "bob", "tavern").
            chain_type: Chain type (e.g., "intention", "resolution", "memory").

        Returns:
            Formatted reasoning string or None if not found.
        """
        if not stats or not stats.results:
            return None

        expected_key = f"{chain_type}:{entity_id}"

        for result in stats.results:
            if result.entity_key == expected_key and result.reasoning_summary:
                # Join reasoning parts
                text = " ".join(result.reasoning_summary)
                return f'{text}'

        return None

    def _had_reasoning_for_entity(
        self, stats: BatchStats | None, entity_id: str, chain_type: str
    ) -> bool:
        """Check if reasoning occurred for specific entity based on reasoning_tokens.

        Note: reasoning_summary may be empty even when reasoning occurred.
        The reliable indicator is reasoning_tokens > 0 in usage.

        Args:
            stats: BatchStats with results.
            entity_id: Entity identifier (e.g., "bob", "tavern").
            chain_type: Chain type (e.g., "intention", "resolution", "memory").

        Returns:
            True if reasoning_tokens > 0 for this entity, False otherwise.
        """
        if not stats or not stats.results:
            return False

        expected_key = f"{chain_type}:{entity_id}"

        for result in stats.results:
            if result.entity_key == expected_key:
                if result.usage and result.usage.reasoning_tokens > 0:
                    return True
                return False

        return False
