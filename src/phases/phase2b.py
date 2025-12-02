"""Phase 2b: Narrative generation (STUB).

Generates narrative text for each location based on what happened.
This stub returns placeholder text.

Example:
    >>> from src.phases.phase2b import execute
    >>> result = await execute(simulation, config, llm_client)
    >>> "[Stub]" in result.data["tavern"]["narrative"]
    True
"""

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient
from src.utils.storage import Simulation

# Type alias (actual Pydantic model will come in B.3b)
NarrativeResponse = dict[str, str]


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,  # Unused in stub
) -> PhaseResult:
    """Generate narratives for all locations (stub: placeholder text).

    Args:
        simulation: Current simulation state.
        config: Application configuration.
        llm_client: LLM client for API calls (unused in stub).

    Returns:
        PhaseResult with data containing dict[str, NarrativeResponse],
        mapping location_id to narrative response.

    Example:
        >>> result = await execute(sim, config, client)
        >>> result.success
        True
    """
    narratives: dict[str, NarrativeResponse] = {}

    for loc_id, location in simulation.locations.items():
        narratives[loc_id] = {"narrative": f"[Stub] Silence hangs over {location.identity.name}."}

    return PhaseResult(success=True, data=narratives)
