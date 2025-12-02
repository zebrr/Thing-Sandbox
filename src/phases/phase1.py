"""Phase 1: Character intentions (STUB).

Generates intentions for all characters. In the real implementation,
each character will receive context and decide what they want to do.
This stub returns 'idle' for everyone.

Example:
    >>> from src.phases.phase1 import execute
    >>> result = await execute(simulation, config, llm_client)
    >>> result.data["bob"]["intention"]
    'idle'
"""

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient
from src.utils.storage import Simulation

# Type alias for clarity (actual Pydantic model will come in B.1b)
IntentionResponse = dict[str, str]


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,  # Unused in stub
) -> PhaseResult:
    """Generate intentions for all characters (stub: returns 'idle' for everyone).

    Args:
        simulation: Current simulation state.
        config: Application configuration.
        llm_client: LLM client for API calls (unused in stub).

    Returns:
        PhaseResult with data containing dict[str, IntentionResponse],
        mapping character_id to intention response.

    Example:
        >>> result = await execute(sim, config, client)
        >>> result.success
        True
    """
    intentions: dict[str, IntentionResponse] = {}

    for char_id in simulation.characters:
        intentions[char_id] = {"intention": "idle"}

    return PhaseResult(success=True, data=intentions)
