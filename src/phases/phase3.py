"""Phase 3: Apply arbitration results.

Applies MasterOutput to simulation state: updates character locations,
internal states, external intents, and collects memory entries for Phase 4.
Pure mechanics, no LLM calls.

Example:
    >>> from src.phases.phase3 import execute
    >>> result = await execute(simulation, config, master_results)
    >>> result.data["pending_memories"]["ogilvy"]
    'I approached the cylinder...'
"""

import logging

from src.config import Config
from src.phases.common import PhaseResult
from src.phases.phase2a import MasterOutput
from src.utils.storage import Simulation

logger = logging.getLogger(__name__)


async def execute(
    simulation: Simulation,
    config: Config,
    master_results: dict[str, MasterOutput],
) -> PhaseResult:
    """Apply arbiter results to simulation state.

    Updates characters (location, internal_state, external_intent) and
    locations (moment, description). Collects memory_entry for each
    character into pending_memories for Phase 4.

    Args:
        simulation: Current simulation state (mutated in place).
        config: Application configuration (unused, for signature consistency).
        master_results: Mapping location_id -> MasterOutput from Phase 2a.

    Returns:
        PhaseResult with success=True and data containing:
        {"pending_memories": {char_id: memory_entry, ...}}

    Example:
        >>> result = await execute(sim, config, master_results)
        >>> result.data["pending_memories"]["bob"]
        'I tried to open the door...'
    """
    pending_memories: dict[str, str] = {}

    for location_id, master_output in master_results.items():
        # Validate location exists
        if location_id not in simulation.locations:
            logger.warning(
                "Phase 3: unknown location '%s' in master_results, skipping",
                location_id,
            )
            continue

        location = simulation.locations[location_id]

        # Apply location updates
        if master_output.location.moment is not None:
            location.state.moment = master_output.location.moment
            logger.debug("Phase 3: updated moment for location '%s'", location_id)

        if master_output.location.description is not None:
            location.identity.description = master_output.location.description
            logger.debug("Phase 3: updated description for location '%s'", location_id)

        # Apply character updates
        for char_id, char_update in master_output.characters.items():
            # Validate character exists
            if char_id not in simulation.characters:
                logger.warning(
                    "Phase 3: unknown character '%s' in location '%s', skipping",
                    char_id,
                    location_id,
                )
                continue

            character = simulation.characters[char_id]

            # Validate target location
            if char_update.location not in simulation.locations:
                logger.warning(
                    "Phase 3: invalid target location '%s' for character '%s', keeping current",
                    char_update.location,
                    char_id,
                )
                # Keep current location, still update other fields
            else:
                character.state.location = char_update.location

            # Update state fields
            character.state.internal_state = char_update.internal_state
            character.state.external_intent = char_update.external_intent

            # Collect memory entry
            pending_memories[char_id] = char_update.memory_entry

            logger.debug("Phase 3: updated character '%s'", char_id)

    return PhaseResult(success=True, data={"pending_memories": pending_memories})
