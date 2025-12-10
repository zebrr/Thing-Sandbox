"""Tick orchestrator for Thing' Sandbox.

Executes one complete tick of simulation: loads state, runs all phases
sequentially, saves results atomically.

Example:
    >>> from pathlib import Path
    >>> from src.config import Config
    >>> from src.narrators import ConsoleNarrator
    >>> from src.runner import TickRunner
    >>> from src.utils.storage import load_simulation
    >>> config = Config.load()
    >>> sim_path = config.project_root / "simulations" / "my-sim"
    >>> simulation = load_simulation(sim_path)
    >>> narrators = [ConsoleNarrator()]
    >>> runner = TickRunner(config, narrators)
    >>> report = await runner.run_tick(simulation, sim_path)
    >>> report.tick_number  # 1
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config import Config, PhaseConfig
from src.phases import (
    execute_phase1,
    execute_phase2a,
    execute_phase2b,
    execute_phase3,
    execute_phase4,
)
from src.utils.llm import BatchStats, LLMClient
from src.utils.llm_adapters import OpenAIAdapter
from src.utils.storage import Simulation, save_simulation

if TYPE_CHECKING:
    from src.narrators import Narrator

logger = logging.getLogger(__name__)

# Timeout for awaiting narrator tasks at end of tick
NARRATOR_TIMEOUT = 30.0


class SimulationBusyError(Exception):
    """Raised when simulation status is 'running'.

    Example:
        >>> raise SimulationBusyError("my-sim")
    """

    def __init__(self, sim_id: str) -> None:
        self.sim_id = sim_id
        super().__init__(f"Simulation '{sim_id}' is busy (status: running)")


class PhaseError(Exception):
    """Raised when any phase fails.

    Example:
        >>> raise PhaseError("phase1", "LLM timeout")
    """

    def __init__(self, phase_name: str, error: str) -> None:
        self.phase_name = phase_name
        self.error = error
        super().__init__(f"Phase {phase_name} failed: {error}")


@dataclass
class PhaseData:
    """Data from single phase execution.

    Attributes:
        duration: Phase execution time in seconds.
        stats: LLM statistics from phase execution, None for Phase 3.
        data: Phase-specific output data.

    Example:
        >>> data = PhaseData(duration=2.1, stats=batch_stats, data=intentions)
    """

    duration: float
    stats: BatchStats | None
    data: Any


@dataclass
class TickReport:
    """Complete tick execution result.

    Used by both narrators (for output) and tick_logger (for detailed logs).

    Attributes:
        sim_id: Simulation identifier.
        tick_number: Completed tick number.
        narratives: Location_id to narrative text mapping.
        location_names: Location_id to display name mapping.
        success: Whether tick completed successfully.
        timestamp: Tick completion time (local).
        duration: Total tick execution time in seconds.
        phases: Phase name to PhaseData mapping.
        simulation: Simulation state after all phases.
        pending_memories: Character_id to memory text from Phase 3.
        error: Error message if success is False.

    Example:
        >>> report = TickReport(
        ...     sim_id="my-sim",
        ...     tick_number=42,
        ...     narratives={"tavern": "Bob enters."},
        ...     location_names={"tavern": "The Rusty Tankard"},
        ...     success=True,
        ...     timestamp=datetime.now(),
        ...     duration=8.2,
        ...     phases={"phase1": phase1_data},
        ...     simulation=sim,
        ...     pending_memories={"bob": "I saw..."},
        ... )
    """

    sim_id: str
    tick_number: int
    narratives: dict[str, str]
    location_names: dict[str, str]
    success: bool
    timestamp: datetime
    duration: float
    phases: dict[str, PhaseData]
    simulation: Simulation
    pending_memories: dict[str, str]
    error: str | None = None


class TickRunner:
    """Main orchestrator for tick execution.

    Executes all phases sequentially, handles errors, and calls narrators.

    Example:
        >>> runner = TickRunner(config, [ConsoleNarrator()])
        >>> result = await runner.run_tick(simulation, sim_path)
    """

    def __init__(self, config: Config, narrators: Sequence[Narrator]) -> None:
        """Initialize tick runner.

        Args:
            config: Application configuration.
            narrators: Sequence of output handlers.
        """
        self._config = config
        self._narrators = narrators

    async def run_tick(self, simulation: Simulation, sim_path: Path) -> TickReport:
        """Execute one complete tick of simulation.

        Flow:
        1. Check status is "paused"
        2. Set status to "running" (in memory)
        3. Create entity dicts for LLM clients
        4. Initialize tick statistics
        5. Execute all phases sequentially
        6. Sync _openai data back to simulation models
        7. Aggregate usage into simulation._openai
        8. Increment current_tick
        9. Set status to "paused"
        10. Save simulation to disk
        11. Log tick completion with statistics
        12. Build TickReport
        13. Write tick log if enabled
        14. Call all narrators
        15. Return TickReport

        Args:
            simulation: Loaded simulation instance.
            sim_path: Path to simulation folder.

        Returns:
            TickReport with tick data, narratives, and phase information.

        Raises:
            SimulationBusyError: Simulation status is "running".
            PhaseError: Any phase failed.
            StorageIOError: Failed to save results.
        """
        start_time = time.time()
        sim_id = simulation.id

        logger.info(
            "Starting tick %d for %s (%d chars, %d locs)",
            simulation.current_tick + 1,
            sim_id,
            len(simulation.characters),
            len(simulation.locations),
        )

        logger.debug("Loaded simulation %s at tick %d", sim_id, simulation.current_tick)

        # Step 2: Check status
        if simulation.status == "running":
            raise SimulationBusyError(sim_id)

        # Step 3: Set status to running (in memory)
        simulation.status = "running"

        # Initialize pending narrator tasks for fire-and-forget pattern
        self._pending_narrator_tasks: list[asyncio.Task[None]] = []

        # Step 3b: Notify narrators of tick start (await - fast, no network)
        await self._notify_tick_start(sim_id, simulation.current_tick + 1, simulation)

        # Step 4: Create entity dicts for LLM clients
        self._create_entity_dicts(simulation)

        # Step 5: Initialize tick statistics
        self._tick_stats = BatchStats()

        # Step 6: Execute all phases
        await self._execute_phases(simulation)

        # Step 7: Sync _openai data back to simulation models
        self._sync_openai_data(simulation)

        # Step 8: Aggregate usage into simulation._openai
        self._aggregate_simulation_usage(simulation)

        # Step 9: Increment current_tick
        simulation.current_tick += 1
        tick_number = simulation.current_tick

        # Step 10: Set status to paused
        simulation.status = "paused"

        # Step 11: Save simulation
        save_simulation(sim_path, simulation)

        # Step 11b: Await pending narrator tasks (fire-and-forget completes here)
        await self._await_pending_narrator_tasks()

        # Step 12: Log tick completion with statistics
        elapsed_time = time.time() - start_time
        logger.info(
            "Tick %d completed (%.1fs, %s tokens, %s reasoning)",
            tick_number,
            elapsed_time,
            f"{self._tick_stats.total_tokens:,}",
            f"{self._tick_stats.reasoning_tokens:,}",
        )

        # Build location_names from simulation
        location_names = {loc_id: loc.identity.name for loc_id, loc in simulation.locations.items()}

        # Step 13: Build TickReport (used by both tick_logger and narrators)
        report = TickReport(
            sim_id=sim_id,
            tick_number=tick_number,
            narratives=self._narratives,
            location_names=location_names,
            success=True,
            timestamp=datetime.now(),
            duration=elapsed_time,
            phases=self._phase_data,
            simulation=simulation,
            pending_memories=self._pending_memories,
        )

        # Step 14: Write tick log if enabled
        if self._config.output.file.enabled:
            from src.tick_logger import TickLogger

            tick_logger = TickLogger(sim_path)
            tick_logger.write(report)
            logger.debug("Wrote tick log: logs/tick_%06d.md", tick_number)

        # Step 15: Call all narrators
        self._call_narrators(report)

        return report

    def _create_entity_dicts(self, simulation: Simulation) -> None:
        """Create entity dicts for LLM clients.

        Converts Pydantic models to dicts and stores them as instance attributes.
        These dicts are mutated by LLMClient during phase execution and later
        synced back to simulation models.

        Args:
            simulation: Simulation to extract entities from.
        """
        self._char_entities: list[dict[str, Any]] = [
            c.model_dump() for c in simulation.characters.values()
        ]
        self._loc_entities: list[dict[str, Any]] = [
            loc.model_dump() for loc in simulation.locations.values()
        ]

    def _create_char_llm_client(self, config: PhaseConfig) -> LLMClient:
        """Create LLM client for character phases (1, 4).

        Args:
            config: Phase configuration with model settings.

        Returns:
            Configured LLMClient with character entities.
        """
        adapter = OpenAIAdapter(config)
        return LLMClient(
            adapter=adapter,
            entities=self._char_entities,
            default_depth=config.response_chain_depth,
        )

    def _create_loc_llm_client(self, config: PhaseConfig) -> LLMClient:
        """Create LLM client for location phases (2a, 2b).

        Args:
            config: Phase configuration with model settings.

        Returns:
            Configured LLMClient with location entities.
        """
        adapter = OpenAIAdapter(config)
        return LLMClient(
            adapter=adapter,
            entities=self._loc_entities,
            default_depth=config.response_chain_depth,
        )

    def _sync_openai_data(self, simulation: Simulation) -> None:
        """Copy _openai data from entity dicts back to Simulation models.

        After phases execute, the entity dicts contain updated _openai data
        (chains and usage). This method copies that data back to the Pydantic
        models so it can be saved via model_dump().

        Args:
            simulation: Simulation to update with _openai data.
        """
        for entity_dict in self._char_entities:
            char_id = entity_dict["identity"]["id"]
            if "_openai" in entity_dict and char_id in simulation.characters:
                char = simulation.characters[char_id]
                extra = char.__pydantic_extra__
                if extra is None:
                    extra = {}
                    object.__setattr__(char, "__pydantic_extra__", extra)
                extra["_openai"] = entity_dict["_openai"]

        for entity_dict in self._loc_entities:
            loc_id = entity_dict["identity"]["id"]
            if "_openai" in entity_dict and loc_id in simulation.locations:
                loc = simulation.locations[loc_id]
                extra = loc.__pydantic_extra__
                if extra is None:
                    extra = {}
                    object.__setattr__(loc, "__pydantic_extra__", extra)
                extra["_openai"] = entity_dict["_openai"]

    def _aggregate_simulation_usage(self, simulation: Simulation) -> None:
        """Sum usage from all entities into simulation._openai.

        Calculates total usage across all characters and locations and stores
        the aggregate in simulation._openai for easy access to simulation-wide
        usage statistics.

        Args:
            simulation: Simulation to update with aggregate usage.
        """
        totals = {
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "cached_tokens": 0,
            "total_requests": 0,
        }

        # Sum from characters
        for char in simulation.characters.values():
            extra = char.__pydantic_extra__ or {}
            openai_data = extra.get("_openai")
            if openai_data and "usage" in openai_data:
                for key in totals:
                    totals[key] += openai_data["usage"].get(key, 0)

        # Sum from locations
        for loc in simulation.locations.values():
            extra = loc.__pydantic_extra__ or {}
            openai_data = extra.get("_openai")
            if openai_data and "usage" in openai_data:
                for key in totals:
                    totals[key] += openai_data["usage"].get(key, 0)

        # Store in simulation (will be saved by storage via model_dump)
        if simulation.__pydantic_extra__ is None:
            object.__setattr__(simulation, "__pydantic_extra__", {"_openai": totals})
        else:
            simulation.__pydantic_extra__["_openai"] = totals

    async def _execute_phases(self, simulation: Simulation) -> None:
        """Execute all phases sequentially.

        Creates separate LLM clients for character and location phases,
        logs statistics after each phase, and accumulates tick-level stats.
        Stores PhaseData for each phase for TickLogger.

        Args:
            simulation: Simulation instance to process.

        Raises:
            PhaseError: If any phase returns success=False.
        """
        # Initialize phase data storage
        self._phase_data: dict[str, PhaseData] = {}

        # Phase 1: Intentions (characters)
        phase1_start = time.time()
        char_client_p1 = self._create_char_llm_client(self._config.phase1)
        result1 = await execute_phase1(simulation, self._config, char_client_p1)
        if not result1.success:
            raise PhaseError("phase1", result1.error or "Unknown error")

        stats = char_client_p1.get_last_batch_stats()
        self._accumulate_tick_stats(stats)
        self._phase_data["phase1"] = PhaseData(
            duration=time.time() - phase1_start,
            stats=stats,
            data=result1.data,
        )
        logging.getLogger("src.phases.phase1").info(
            "Completed (%d chars, %s tokens, %s reasoning)",
            len(simulation.characters),
            f"{stats.total_tokens:,}",
            f"{stats.reasoning_tokens:,}",
        )
        self._notify_phase_complete("phase1", self._phase_data["phase1"])

        # Extract intention strings for Phase 2a/2b
        intentions_str = {char_id: resp.intention for char_id, resp in result1.data.items()}

        # Phase 2a: Scene resolution (locations)
        phase2a_start = time.time()
        loc_client_p2a = self._create_loc_llm_client(self._config.phase2a)
        result2a = await execute_phase2a(simulation, self._config, loc_client_p2a, intentions_str)
        if not result2a.success:
            raise PhaseError("phase2a", result2a.error or "Unknown error")

        stats = loc_client_p2a.get_last_batch_stats()
        self._accumulate_tick_stats(stats)
        self._phase_data["phase2a"] = PhaseData(
            duration=time.time() - phase2a_start,
            stats=stats,
            data=result2a.data,
        )
        logging.getLogger("src.phases.phase2a").info(
            "Completed (%d locs, %s tokens, %s reasoning)",
            len(simulation.locations),
            f"{stats.total_tokens:,}",
            f"{stats.reasoning_tokens:,}",
        )
        self._notify_phase_complete("phase2a", self._phase_data["phase2a"])

        # Phase 2b: Narrative generation (locations)
        phase2b_start = time.time()
        loc_client_p2b = self._create_loc_llm_client(self._config.phase2b)
        result2b = await execute_phase2b(
            simulation, self._config, loc_client_p2b, result2a.data, intentions_str
        )
        if not result2b.success:
            raise PhaseError("phase2b", result2b.error or "Unknown error")

        stats = loc_client_p2b.get_last_batch_stats()
        self._accumulate_tick_stats(stats)
        self._phase_data["phase2b"] = PhaseData(
            duration=time.time() - phase2b_start,
            stats=stats,
            data=result2b.data,
        )
        logging.getLogger("src.phases.phase2b").info(
            "Completed (%d locs, %s tokens, %s reasoning)",
            len(simulation.locations),
            f"{stats.total_tokens:,}",
            f"{stats.reasoning_tokens:,}",
        )
        self._notify_phase_complete("phase2b", self._phase_data["phase2b"])

        # Extract narratives for TickResult
        self._narratives: dict[str, str] = {}
        for loc_id, narrative_resp in result2b.data.items():
            self._narratives[loc_id] = narrative_resp.narrative

        # Phase 3: Apply results (no LLM, pure mechanics)
        phase3_start = time.time()
        result3 = await execute_phase3(simulation, self._config, result2a.data)
        if not result3.success:
            raise PhaseError("phase3", result3.error or "Unknown error")

        self._phase_data["phase3"] = PhaseData(
            duration=time.time() - phase3_start,
            stats=None,
            data=result3.data,
        )
        logging.getLogger("src.phases.phase3").info("Completed (results applied)")
        self._notify_phase_complete("phase3", self._phase_data["phase3"])

        # Phase 4: Memory update (characters)
        phase4_start = time.time()
        self._pending_memories = result3.data["pending_memories"]
        char_client_p4 = self._create_char_llm_client(self._config.phase4)
        result4 = await execute_phase4(
            simulation, self._config, char_client_p4, self._pending_memories
        )
        if not result4.success:
            raise PhaseError("phase4", result4.error or "Unknown error")

        stats = char_client_p4.get_last_batch_stats()
        self._accumulate_tick_stats(stats)
        self._phase_data["phase4"] = PhaseData(
            duration=time.time() - phase4_start,
            stats=stats,
            data=result4.data,
        )
        logging.getLogger("src.phases.phase4").info(
            "Completed (%d chars, %s tokens, %s reasoning)",
            len(simulation.characters),
            f"{stats.total_tokens:,}",
            f"{stats.reasoning_tokens:,}",
        )
        self._notify_phase_complete("phase4", self._phase_data["phase4"])

    def _accumulate_tick_stats(self, phase_stats: BatchStats) -> None:
        """Add phase statistics to tick totals.

        Args:
            phase_stats: Statistics from completed phase.
        """
        self._tick_stats.total_tokens += phase_stats.total_tokens
        self._tick_stats.reasoning_tokens += phase_stats.reasoning_tokens
        self._tick_stats.cached_tokens += phase_stats.cached_tokens
        self._tick_stats.request_count += phase_stats.request_count
        self._tick_stats.success_count += phase_stats.success_count
        self._tick_stats.error_count += phase_stats.error_count

    def _call_narrators(self, report: TickReport) -> None:
        """Call all narrators with report.

        Narrator failures are logged but don't affect tick result.

        Args:
            report: TickReport to output.
        """
        for narrator in self._narrators:
            try:
                narrator.output(report)
            except Exception as e:
                logger.error("Narrator %s failed: %s", type(narrator).__name__, e)

    async def _notify_tick_start(
        self, sim_id: str, tick_number: int, simulation: Simulation
    ) -> None:
        """Notify all narrators that tick is starting.

        Called synchronously (awaited) because it's fast and narrators may need
        to store simulation reference before phases run.

        Args:
            sim_id: Simulation identifier.
            tick_number: Tick number about to execute.
            simulation: Simulation instance.
        """
        for narrator in self._narrators:
            try:
                await narrator.on_tick_start(sim_id, tick_number, simulation)
            except Exception as e:
                logger.error("Narrator %s on_tick_start failed: %s", type(narrator).__name__, e)

    def _notify_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """Schedule narrator notifications for phase completion.

        Uses fire-and-forget pattern: creates tasks but doesn't await them.
        Tasks are collected in self._pending_narrator_tasks and awaited
        at end of tick via _await_pending_narrator_tasks().

        Args:
            phase_name: Name of completed phase.
            phase_data: Phase execution data.
        """
        for narrator in self._narrators:
            task = asyncio.create_task(self._safe_phase_complete(narrator, phase_name, phase_data))
            self._pending_narrator_tasks.append(task)

    async def _safe_phase_complete(
        self, narrator: Narrator, phase_name: str, phase_data: PhaseData
    ) -> None:
        """Wrapper to catch exceptions from narrator.on_phase_complete.

        Args:
            narrator: Narrator instance to notify.
            phase_name: Name of completed phase.
            phase_data: Phase execution data.
        """
        try:
            await narrator.on_phase_complete(phase_name, phase_data)
        except Exception as e:
            logger.error("Narrator %s on_phase_complete failed: %s", type(narrator).__name__, e)

    async def _await_pending_narrator_tasks(self) -> None:
        """Wait for all pending narrator tasks with timeout.

        Called at end of tick after save. In normal scenario tasks are already
        done (phases take ~10s, enough for Telegram). Timeout is safety net.
        """
        if not self._pending_narrator_tasks:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*self._pending_narrator_tasks, return_exceptions=True),
                timeout=NARRATOR_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Narrator tasks timed out after %.1fs (%d tasks pending)",
                NARRATOR_TIMEOUT,
                len([t for t in self._pending_narrator_tasks if not t.done()]),
            )
        finally:
            self._pending_narrator_tasks.clear()
