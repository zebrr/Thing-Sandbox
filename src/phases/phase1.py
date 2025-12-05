"""Phase 1: Character intentions.

Generates intentions for all characters. Each character receives context
(identity, state, memory, location, others) and decides what they want to do.
Uses LLM batch execution with fallback to "idle" on errors.

Example:
    >>> from src.phases.phase1 import execute, IntentionResponse
    >>> result = await execute(simulation, config, llm_client)
    >>> result.data["bob"].intention
    'I want to explore the forest'
"""

import logging

from pydantic import BaseModel

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient, LLMRequest
from src.utils.llm_errors import LLMError
from src.utils.prompts import PromptRenderer
from src.utils.storage import Character, Simulation

logger = logging.getLogger(__name__)


class IntentionResponse(BaseModel):
    """LLM structured output for character intention.

    Corresponds to src/schemas/IntentionResponse.schema.json.

    Example:
        >>> response = IntentionResponse(intention="I will explore the cave")
        >>> response.intention
        'I will explore the cave'
    """

    intention: str


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
) -> PhaseResult:
    """Generate intentions for all characters.

    For each character:
    1. Validates location exists (fallback to idle if not)
    2. Assembles context (identity, state, memory, location, others)
    3. Renders system and user prompts
    4. Creates LLM request with structured output

    All requests are executed in parallel via batch. Failed requests
    fall back to "idle" intention with warning and console message.

    Args:
        simulation: Current simulation state with characters and locations.
        config: Application configuration.
        llm_client: LLM client for API calls.

    Returns:
        PhaseResult with success=True and data containing dict[str, IntentionResponse],
        mapping character_id to intention response.

    Example:
        >>> result = await execute(sim, config, client)
        >>> result.success
        True
        >>> result.data["ogilvy"].intention
        'Approach the cylinder cautiously...'
    """
    # Create PromptRenderer with simulation path for override resolution
    sim_path = config._project_root / "simulations" / simulation.id
    renderer = PromptRenderer(config, sim_path=sim_path)

    # Group characters by location for efficient "others" lookup
    location_groups = _group_by_location(simulation.characters)

    # Collect valid characters and build requests; invalid get immediate fallback
    characters = list(simulation.characters.values())
    valid_chars: list[Character] = []
    requests: list[LLMRequest] = []
    intentions: dict[str, IntentionResponse] = {}

    for char in characters:
        char_id = char.identity.id
        location = simulation.locations.get(char.state.location)

        if location is None:
            # Invalid location → immediate fallback
            logger.warning(
                "Phase 1: %s fallback to idle (invalid location: %s)",
                char_id,
                char.state.location,
            )
            print(
                f"\u26a0\ufe0f  Phase 1: {char_id} fallback to idle "
                f"(invalid location: {char.state.location})"
            )
            intentions[char_id] = IntentionResponse(intention="idle")
            continue

        # Valid character — build request
        valid_chars.append(char)

        # Get others in same location (excluding self)
        others_in_location = location_groups.get(char.state.location, [])
        others = [c for c in others_in_location if c.identity.id != char_id]

        # Render prompts
        system_prompt = renderer.render("phase1_intention_system", {})
        user_prompt = renderer.render(
            "phase1_intention_user",
            {
                "character": char,
                "location": location,
                "others": others,
            },
        )

        # Create request
        requests.append(
            LLMRequest(
                instructions=system_prompt,
                input_data=user_prompt,
                schema=IntentionResponse,
                entity_key=f"intention:{char_id}",
            )
        )

    # Execute batch for valid characters only
    if requests:
        results = await llm_client.create_batch(requests)

        # Process results with fallback for errors
        for char, result in zip(valid_chars, results):
            char_id = char.identity.id
            if isinstance(result, LLMError):
                error_type = type(result).__name__
                logger.warning("Phase 1: %s fallback to idle (%s: %s)", char_id, error_type, result)
                print(f"\u26a0\ufe0f  Phase 1: {char_id} fallback to idle ({error_type}: {result})")
                intentions[char_id] = IntentionResponse(intention="idle")
            else:
                intentions[char_id] = result  # type: ignore[assignment]

    return PhaseResult(success=True, data=intentions)
