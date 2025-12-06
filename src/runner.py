"""Tick orchestrator for Thing' Sandbox.

Executes one complete tick of simulation: loads state, runs all phases
sequentially, saves results atomically.

Example:
    >>> from src.config import Config
    >>> from src.narrators import ConsoleNarrator
    >>> from src.runner import TickRunner
    >>> config = Config.load()
    >>> narrators = [ConsoleNarrator()]
    >>> runner = TickRunner(config, narrators)
    >>> result = await runner.run_tick("my-sim")
    >>> print(f"Completed tick {result.tick_number}")
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
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
from src.utils.storage import Simulation, load_simulation, save_simulation

if TYPE_CHECKING:
    from src.narrators import Narrator

logger = logging.getLogger(__name__)


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
class TickResult:
    """Result of a completed tick.

    Attributes:
        sim_id: Simulation identifier.
        tick_number: Completed tick number.
        narratives: Mapping of location_id to narrative text.
        location_names: Mapping of location_id to display name.
        success: Whether tick completed successfully.
        error: Error message if success is False.

    Example:
        >>> result = TickResult(
        ...     sim_id="my-sim",
        ...     tick_number=42,
        ...     narratives={"tavern": "Bob enters."},
        ...     location_names={"tavern": "The Rusty Tankard"},
        ...     success=True,
        ... )
    """

    sim_id: str
    tick_number: int
    narratives: dict[str, str]
    location_names: dict[str, str]
    success: bool
    error: str | None = None


class TickRunner:
    """Main orchestrator for tick execution.

    Executes all phases sequentially, handles errors, and calls narrators.

    Example:
        >>> runner = TickRunner(config, [ConsoleNarrator()])
        >>> result = await runner.run_tick("my-sim")
    """

    def __init__(self, config: Config, narrators: Sequence[Narrator]) -> None:
        """Initialize tick runner.

        Args:
            config: Application configuration.
            narrators: Sequence of output handlers.
        """
        self._config = config
        self._narrators = narrators

    async def run_tick(self, sim_id: str) -> TickResult:
        """Execute one complete tick of simulation.

        Flow:
        1. Resolve path and load simulation
        2. Check status is "paused"
        3. Set status to "running" (in memory)
        4. Create entity dicts for LLM clients
        5. Initialize tick statistics
        6. Execute all phases sequentially
        7. Sync _openai data back to simulation models
        8. Aggregate usage into simulation._openai
        9. Increment current_tick
        10. Set status to "paused"
        11. Save simulation to disk
        12. Log tick completion with statistics
        13. Call all narrators
        14. Return TickResult

        Args:
            sim_id: Simulation identifier.

        Returns:
            TickResult with tick data and narratives.

        Raises:
            SimulationNotFoundError: Simulation doesn't exist.
            SimulationBusyError: Simulation status is "running".
            PhaseError: Any phase failed.
            StorageIOError: Failed to save results.
        """
        start_time = time.time()

        # Step 1: Resolve path and load simulation
        sim_path = self._config.project_root / "simulations" / sim_id
        simulation = load_simulation(sim_path)

        logger.debug("Loaded simulation %s at tick %d", sim_id, simulation.current_tick)

        # Step 2: Check status
        if simulation.status == "running":
            raise SimulationBusyError(sim_id)

        # Step 3: Set status to running (in memory)
        simulation.status = "running"

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

        # Step 12: Log tick completion with statistics
        elapsed_time = time.time() - start_time
        logger.info(
            "🎬 runner: Tick %d complete (%.1fs, %s tokens, %s reasoning)",
            tick_number,
            elapsed_time,
            f"{self._tick_stats.total_tokens:,}",
            f"{self._tick_stats.reasoning_tokens:,}",
        )

        # Build narratives and location_names from simulation
        narratives = self._narratives
        location_names = {loc_id: loc.identity.name for loc_id, loc in simulation.locations.items()}

        # Step 13: Build result
        result = TickResult(
            sim_id=sim_id,
            tick_number=tick_number,
            narratives=narratives,
            location_names=location_names,
            success=True,
        )

        # Step 14: Call all narrators
        self._call_narrators(result)

        return result

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

        Args:
            simulation: Simulation instance to process.

        Raises:
            PhaseError: If any phase returns success=False.
        """
        # Phase 1: Intentions (characters)
        char_client_p1 = self._create_char_llm_client(self._config.phase1)
        result1 = await execute_phase1(simulation, self._config, char_client_p1)
        if not result1.success:
            raise PhaseError("phase1", result1.error or "Unknown error")

        stats = char_client_p1.get_last_batch_stats()
        self._accumulate_tick_stats(stats)
        logger.info(
            "🎭 phase1: Complete (%d chars, %s tokens, %s reasoning)",
            len(simulation.characters),
            f"{stats.total_tokens:,}",
            f"{stats.reasoning_tokens:,}",
        )

        # Phase 2a: Scene resolution (locations)
        loc_client_p2a = self._create_loc_llm_client(self._config.phase2a)
        result2a = await execute_phase2a(simulation, self._config, loc_client_p2a)
        if not result2a.success:
            raise PhaseError("phase2a", result2a.error or "Unknown error")

        stats = loc_client_p2a.get_last_batch_stats()
        self._accumulate_tick_stats(stats)
        logger.info(
            "⚖️ phase2a: Complete (%d locs, %s tokens, %s reasoning)",
            len(simulation.locations),
            f"{stats.total_tokens:,}",
            f"{stats.reasoning_tokens:,}",
        )

        # Phase 2b: Narrative generation (still stub, passes None)
        # Infrastructure ready, but phase 2b implementation is a separate task
        result2b = await execute_phase2b(simulation, self._config, None)  # type: ignore[arg-type]
        if not result2b.success:
            raise PhaseError("phase2b", result2b.error or "Unknown error")
        logger.info("📖 phase2b: Complete (%d narratives, stub)", len(result2b.data))

        # Extract narratives for TickResult
        self._narratives: dict[str, str] = {}
        for loc_id, data in result2b.data.items():
            self._narratives[loc_id] = data.get("narrative", "")

        # Phase 3: Apply results (no LLM, pure mechanics)
        result3 = await execute_phase3(simulation, self._config, result2a.data)
        if not result3.success:
            raise PhaseError("phase3", result3.error or "Unknown error")
        logger.info("⚡ phase3: Complete (results applied)")

        # Phase 4: Memory update (characters)
        pending_memories = result3.data["pending_memories"]
        char_client_p4 = self._create_char_llm_client(self._config.phase4)
        result4 = await execute_phase4(simulation, self._config, char_client_p4, pending_memories)
        if not result4.success:
            raise PhaseError("phase4", result4.error or "Unknown error")

        stats = char_client_p4.get_last_batch_stats()
        self._accumulate_tick_stats(stats)
        logger.info(
            "🧠 phase4: Complete (%d chars, %s tokens, %s reasoning)",
            len(simulation.characters),
            f"{stats.total_tokens:,}",
            f"{stats.reasoning_tokens:,}",
        )

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

    def _call_narrators(self, result: TickResult) -> None:
        """Call all narrators with result.

        Narrator failures are logged but don't affect tick result.

        Args:
            result: TickResult to output.
        """
        for narrator in self._narrators:
            try:
                narrator.output(result)
            except Exception as e:
                logger.error("Narrator %s failed: %s", type(narrator).__name__, e)
