"""Phase 2a: Scene arbitration (STUB).

Resolves scenes in all locations. The game master (arbiter) determines
what happens when characters with intentions interact. This stub
returns minimal output with no changes.

Example:
    >>> from src.phases.phase2a import execute
    >>> result = await execute(simulation, config, llm_client)
    >>> result.data["tavern"]["location_id"]
    'tavern'
"""

from typing import Any

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient
from src.utils.storage import Simulation

# Type alias (actual Pydantic model will come in B.3b)
MasterOutput = dict[str, Any]


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,  # Unused in stub
) -> PhaseResult:
    """Resolve scenes in all locations (stub: no changes).

    Args:
        simulation: Current simulation state.
        config: Application configuration.
        llm_client: LLM client for API calls (unused in stub).

    Returns:
        PhaseResult with data containing dict[str, MasterOutput],
        mapping location_id to master result.

    Example:
        >>> result = await execute(sim, config, client)
        >>> result.success
        True
    """
    results: dict[str, MasterOutput] = {}

    for loc_id, location in simulation.locations.items():
        # Find characters in this location
        chars_here = {
            char_id: char
            for char_id, char in simulation.characters.items()
            if char.state.location == loc_id
        }

        # Build minimal Master output
        char_updates = {}
        for char_id, char in chars_here.items():
            char_updates[char_id] = {
                "location": char.state.location,  # No movement
                "internal_state": char.state.internal_state or "",
                "external_intent": char.state.external_intent or "",
                "memory_entry": "[Stub] Nothing notable happened.",
            }

        results[loc_id] = {
            "tick": simulation.current_tick,
            "location_id": loc_id,
            "characters": char_updates,
            "location": {
                "moment": None,  # No change
                "description": None,  # No change
            },
        }

    return PhaseResult(success=True, data=results)
