"""Phase 2a: Scene arbitration.

Resolves scenes in all locations. The game master (arbiter) determines
what happens when characters with intentions interact. Processes all
locations in parallel via batch execution, handles failures with fallback.

Example:
    >>> from src.phases.phase2a import execute, MasterOutput
    >>> result = await execute(simulation, config, llm_client, intentions)
    >>> result.data["tavern"].location_id
    'tavern'
"""

import logging

from pydantic import BaseModel, Field

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient, LLMRequest
from src.utils.llm_errors import LLMError
from src.utils.prompts import PromptRenderer
from src.utils.storage import Character, Simulation

logger = logging.getLogger(__name__)


class CharacterUpdate(BaseModel):
    """Update for a single character from arbiter.

    Example:
        >>> update = CharacterUpdate(
        ...     character_id="bob",
        ...     location="forest",
        ...     internal_state="Tired",
        ...     external_intent="Rest",
        ...     memory_entry="I walked to the forest..."
        ... )
    """

    character_id: str
    location: str
    internal_state: str
    external_intent: str
    memory_entry: str = Field(..., min_length=1)


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

    Note: characters is a list (not dict) because OpenAI Structured Outputs
    does not support dicts with dynamic keys. Use characters_dict property
    for dict access.

    Example:
        >>> output = MasterOutput(
        ...     tick=5,
        ...     location_id="tavern",
        ...     characters=[CharacterUpdate(
        ...         character_id="bob",
        ...         location="tavern",
        ...         internal_state="Happy",
        ...         external_intent="Drink ale",
        ...         memory_entry="I ordered a drink"
        ...     )],
        ...     location=LocationUpdate()
        ... )
        >>> output.characters_dict["bob"].location
        'tavern'
    """

    tick: int
    location_id: str
    characters: list[CharacterUpdate]
    location: LocationUpdate

    @property
    def characters_dict(self) -> dict[str, CharacterUpdate]:
        """Convert characters list to dict keyed by character_id."""
        return {cu.character_id: cu for cu in self.characters}


def _group_by_location(characters: dict[str, Character]) -> dict[str, list[Character]]:
    """Group characters by their current location.

    Args:
        characters: Dictionary of characters keyed by ID.

    Returns:
        Dictionary mapping location_id to list of characters at that location.

    Example:
        >>> chars = {"bob": bob_char, "alice": alice_char}
        >>> groups = _group_by_location(chars)
        >>> groups["tavern"]
        [<Character bob>, <Character alice>]
    """
    groups: dict[str, list[Character]] = {}
    for char in characters.values():
        loc_id = char.state.location
        if loc_id not in groups:
            groups[loc_id] = []
        groups[loc_id].append(char)
    return groups


def _create_fallback(
    simulation: Simulation,
    loc_id: str,
    chars_here: dict[str, Character],
) -> MasterOutput:
    """Create fallback MasterOutput when LLM fails.

    Args:
        simulation: Current simulation state.
        loc_id: Location ID for this fallback.
        chars_here: Characters in this location.

    Returns:
        MasterOutput with preserved current state.
    """
    char_updates: list[CharacterUpdate] = []
    for char_id, char in chars_here.items():
        char_updates.append(
            CharacterUpdate(
                character_id=char_id,
                location=char.state.location,
                internal_state=char.state.internal_state or "",
                external_intent=char.state.external_intent or "",
                memory_entry="[No resolution — simulation continues]",
            )
        )
    return MasterOutput(
        tick=simulation.current_tick,
        location_id=loc_id,
        characters=char_updates,
        location=LocationUpdate(moment=None, description=None),
    )


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
    intentions: dict[str, str],
) -> PhaseResult:
    """Resolve scenes in all locations.

    For each location:
    1. Collects characters currently at this location
    2. Gathers their intentions
    3. Renders arbiter prompts with full context
    4. Creates LLM request with structured output

    All requests are executed in parallel via batch. Failed requests
    fall back to preserving current state with warning log.

    Args:
        simulation: Current simulation state with characters and locations.
        config: Application configuration.
        llm_client: LLM client for API calls.
        intentions: Character intentions from Phase 1 (char_id -> intention string).

    Returns:
        PhaseResult with success=True and data containing dict[str, MasterOutput],
        mapping location_id to arbiter result.

    Example:
        >>> result = await execute(sim, config, client, intentions)
        >>> result.success
        True
        >>> result.data["tavern"].characters["bob"].memory_entry
        'I approached the stranger...'
    """
    # Create PromptRenderer with simulation path for override resolution
    sim_path = config.project_root / "simulations" / simulation.id
    renderer = PromptRenderer(config, sim_path=sim_path)

    # Group characters by location for efficient lookup
    location_groups = _group_by_location(simulation.characters)

    # Build requests for each location
    requests: list[LLMRequest] = []
    location_ids: list[str] = []
    chars_per_location: list[dict[str, Character]] = []

    for loc_id, location in simulation.locations.items():
        # Find characters in this location
        chars_here = {char.identity.id: char for char in location_groups.get(loc_id, [])}

        # Extract intentions for characters in this location
        loc_intentions = {char_id: intentions.get(char_id, "idle") for char_id in chars_here}

        # Render prompts
        system_prompt = renderer.render("phase2a_resolution_system", {})
        user_prompt = renderer.render(
            "phase2a_resolution_user",
            {
                "location": location,
                "characters": list(chars_here.values()),
                "intentions": loc_intentions,
                "simulation": simulation,
            },
        )

        # Create request
        requests.append(
            LLMRequest(
                instructions=system_prompt,
                input_data=user_prompt,
                schema=MasterOutput,
                entity_key=f"resolution:{loc_id}",
            )
        )
        location_ids.append(loc_id)
        chars_per_location.append(chars_here)

    # Execute batch
    results: dict[str, MasterOutput] = {}

    if requests:
        batch_results = await llm_client.create_batch(requests)

        # Process results with fallback for errors
        for loc_id, chars_here, result in zip(location_ids, chars_per_location, batch_results):
            if isinstance(result, LLMError):
                error_type = type(result).__name__
                logger.warning(
                    "Phase 2a: %s fallback (%s: %s)",
                    loc_id,
                    error_type,
                    result,
                )
                results[loc_id] = _create_fallback(simulation, loc_id, chars_here)
            else:
                results[loc_id] = result  # type: ignore[assignment]

    return PhaseResult(success=True, data=results)
