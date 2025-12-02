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
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.config import Config
from src.phases import (
    execute_phase1,
    execute_phase2a,
    execute_phase2b,
    execute_phase3,
    execute_phase4,
)
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
        4. Execute all phases sequentially
        5. Extract narratives from phase2b
        6. Increment current_tick
        7. Set status to "paused"
        8. Save simulation to disk
        9. Call all narrators
        10. Return TickResult

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
        # Step 1: Resolve path and load simulation
        sim_path = self._config._project_root / "simulations" / sim_id
        simulation = load_simulation(sim_path)

        logger.debug("Loaded simulation %s at tick %d", sim_id, simulation.current_tick)

        # Step 2: Check status
        if simulation.status == "running":
            raise SimulationBusyError(sim_id)

        # Step 3: Set status to running (in memory)
        simulation.status = "running"

        # Step 4: Execute all phases
        await self._execute_phases(simulation)

        # Step 5: Extract narratives from phase2b (done in _execute_phases)
        # Phase2b result is stored during execution

        # Step 6: Increment current_tick
        simulation.current_tick += 1
        tick_number = simulation.current_tick

        # Step 7: Set status to paused
        simulation.status = "paused"

        # Step 8: Save simulation
        save_simulation(sim_path, simulation)
        logger.info("Saved simulation %s at tick %d", sim_id, tick_number)

        # Build narratives and location_names from simulation
        narratives = self._narratives
        location_names = {loc_id: loc.identity.name for loc_id, loc in simulation.locations.items()}

        # Step 9: Build result
        result = TickResult(
            sim_id=sim_id,
            tick_number=tick_number,
            narratives=narratives,
            location_names=location_names,
            success=True,
        )

        # Step 10: Call all narrators
        self._call_narrators(result)

        return result

    async def _execute_phases(self, simulation: Simulation) -> None:
        """Execute all phases sequentially.

        Args:
            simulation: Simulation instance to process.

        Raises:
            PhaseError: If any phase returns success=False.
        """
        # Phase 1: Intentions
        result1 = await execute_phase1(simulation, self._config, None)  # type: ignore[arg-type]
        if not result1.success:
            raise PhaseError("phase1", result1.error or "Unknown error")
        logger.debug("Phase 1 completed: %d intentions", len(result1.data))

        # Phase 2a: Scene resolution
        result2a = await execute_phase2a(simulation, self._config, None)  # type: ignore[arg-type]
        if not result2a.success:
            raise PhaseError("phase2a", result2a.error or "Unknown error")
        logger.debug("Phase 2a completed: %d locations", len(result2a.data))

        # Phase 2b: Narrative generation
        result2b = await execute_phase2b(simulation, self._config, None)  # type: ignore[arg-type]
        if not result2b.success:
            raise PhaseError("phase2b", result2b.error or "Unknown error")
        logger.debug("Phase 2b completed: %d narratives", len(result2b.data))

        # Extract narratives for TickResult
        self._narratives: dict[str, str] = {}
        for loc_id, data in result2b.data.items():
            self._narratives[loc_id] = data.get("narrative", "")

        # Phase 3: Apply results
        result3 = await execute_phase3(simulation, self._config, None)  # type: ignore[arg-type]
        if not result3.success:
            raise PhaseError("phase3", result3.error or "Unknown error")
        logger.debug("Phase 3 completed")

        # Phase 4: Memory update
        result4 = await execute_phase4(simulation, self._config, None)  # type: ignore[arg-type]
        if not result4.success:
            raise PhaseError("phase4", result4.error or "Unknown error")
        logger.debug("Phase 4 completed")

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
