"""Phase 2a: Scene arbitration (STUB).

Resolves scenes in all locations. The game master (arbiter) determines
what happens when characters with intentions interact. This stub
returns minimal output with no changes.

Example:
    >>> from src.phases.phase2a import execute, MasterOutput
    >>> result = await execute(simulation, config, llm_client)
    >>> result.data["tavern"].location_id
    'tavern'
"""

from pydantic import BaseModel

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient
from src.utils.storage import Simulation


class CharacterUpdate(BaseModel):
    """Update for a single character from arbiter.

    Example:
        >>> update = CharacterUpdate(
        ...     location="forest",
        ...     internal_state="Tired",
        ...     external_intent="Rest",
        ...     memory_entry="I walked to the forest..."
        ... )
    """

    location: str
    internal_state: str
    external_intent: str
    memory_entry: str


class LocationUpdate(BaseModel):
    """Update for location state from arbiter.

    Example:
        >>> update = LocationUpdate(moment="Evening falls")
    """

    moment: str | None = None
    description: str | None = None


class MasterOutput(BaseModel):
    """Complete arbiter output for one location.

    Corresponds to src/schemas/Master.schema.json.

    Example:
        >>> output = MasterOutput(
        ...     tick=5,
        ...     location_id="tavern",
        ...     characters={"bob": CharacterUpdate(
        ...         location="tavern",
        ...         internal_state="Happy",
        ...         external_intent="Drink ale",
        ...         memory_entry="I ordered a drink"
        ...     )},
        ...     location=LocationUpdate()
        ... )
    """

    tick: int
    location_id: str
    characters: dict[str, CharacterUpdate]
    location: LocationUpdate


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

        # Build minimal Master output with Pydantic models
        char_updates: dict[str, CharacterUpdate] = {}
        for char_id, char in chars_here.items():
            char_updates[char_id] = CharacterUpdate(
                location=char.state.location,  # No movement
                internal_state=char.state.internal_state or "",
                external_intent=char.state.external_intent or "",
                memory_entry="[Stub] Nothing notable happened.",
            )

        results[loc_id] = MasterOutput(
            tick=simulation.current_tick,
            location_id=loc_id,
            characters=char_updates,
            location=LocationUpdate(moment=None, description=None),
        )

    return PhaseResult(success=True, data=results)
