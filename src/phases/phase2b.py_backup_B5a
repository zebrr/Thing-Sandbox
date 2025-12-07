"""Phase 2b: Narrative generation.

Generates narrative text for each location based on arbiter decisions.
Transforms MasterOutput into human-readable prose for the observer log.
Processes all locations in parallel via batch execution.

Example:
    >>> from src.phases.phase2b import execute, NarrativeResponse
    >>> result = await execute(simulation, config, llm_client, master_results, intentions)
    >>> result.data["tavern"].narrative
    'The morning sun cast long shadows...'
"""

import logging

from pydantic import BaseModel, Field

from src.config import Config
from src.phases.common import PhaseResult
from src.phases.phase2a import LocationUpdate, MasterOutput
from src.utils.llm import LLMClient, LLMRequest
from src.utils.llm_errors import LLMError
from src.utils.prompts import PromptRenderer
from src.utils.storage import Character, Simulation

logger = logging.getLogger(__name__)


class NarrativeResponse(BaseModel):
    """LLM structured output for location narrative.

    Corresponds to src/schemas/NarrativeResponse.schema.json.

    Example:
        >>> response = NarrativeResponse(narrative="The sun set over the hills...")
        >>> response.narrative
        'The sun set over the hills...'
    """

    narrative: str = Field(..., min_length=1)


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


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
    master_results: dict[str, MasterOutput],
    intentions: dict[str, str],
) -> PhaseResult:
    """Generate narratives for all locations.

    For each location:
    1. Collects "before" state (characters before Phase 3 changes)
    2. Gets MasterOutput from arbiter (what will happen)
    3. Gets intentions (what characters wanted)
    4. Renders narrator prompts with transition context
    5. Creates LLM request with structured output

    All requests are executed in parallel via batch. Failed requests
    fall back to placeholder narrative with warning log.

    Args:
        simulation: Current simulation state (BEFORE Phase 3 applies changes).
        config: Application configuration.
        llm_client: LLM client for API calls.
        master_results: Arbiter decisions from Phase 2a (location_id -> MasterOutput).
        intentions: Character intentions from Phase 1 (char_id -> intention string).

    Returns:
        PhaseResult with success=True and data containing dict[str, NarrativeResponse],
        mapping location_id to narrative response.

    Example:
        >>> result = await execute(sim, config, client, master_results, intentions)
        >>> result.success
        True
        >>> result.data["tavern"].narrative
        'Bob stepped into the tavern...'
    """
    # Create PromptRenderer with simulation path for override resolution
    sim_path = config.project_root / "simulations" / simulation.id
    renderer = PromptRenderer(config, sim_path=sim_path)

    # Group characters by location for "before" state
    location_groups = _group_by_location(simulation.characters)

    # Build requests for each location
    requests: list[LLMRequest] = []
    location_ids: list[str] = []

    for loc_id, location in simulation.locations.items():
        # Get characters in this location (before state)
        chars_before = location_groups.get(loc_id, [])

        # Get MasterOutput for this location
        master_result = master_results.get(loc_id)
        if master_result is None:
            # Missing master result — log warning, use empty MasterOutput
            logger.warning(
                "Phase 2b: %s missing MasterOutput, using empty",
                loc_id,
            )
            master_result = MasterOutput(
                tick=simulation.current_tick,
                location_id=loc_id,
                characters=[],
                location=LocationUpdate(),
            )

        # Extract intentions for characters in this location
        loc_intentions = {
            char.identity.id: intentions.get(char.identity.id, "idle") for char in chars_before
        }

        # Render prompts
        system_prompt = renderer.render("phase2b_narrative_system", {})
        user_prompt = renderer.render(
            "phase2b_narrative_user",
            {
                "location_before": location,
                "characters_before": chars_before,
                "master_result": master_result,
                "intentions": loc_intentions,
            },
        )

        # Create request
        requests.append(
            LLMRequest(
                instructions=system_prompt,
                input_data=user_prompt,
                schema=NarrativeResponse,
                entity_key=f"narrative:{loc_id}",
            )
        )
        location_ids.append(loc_id)

    # Execute batch
    results: dict[str, NarrativeResponse] = {}

    if requests:
        batch_results = await llm_client.create_batch(requests)

        # Process results with fallback for errors
        for loc_id, result in zip(location_ids, batch_results):
            if isinstance(result, LLMError):
                error_type = type(result).__name__
                logger.warning(
                    "Phase 2b: %s fallback (%s: %s)",
                    loc_id,
                    error_type,
                    result,
                )
                results[loc_id] = NarrativeResponse(narrative="[Silence in the location]")
            else:
                results[loc_id] = result  # type: ignore[assignment]

    return PhaseResult(success=True, data=results)
