"""Phase 3: Apply arbitration results (STUB).

Applies Master output to simulation state: updates character locations,
internal states, external intents, and adds memory entries.
This stub is a no-op.

Example:
    >>> from src.phases.phase3 import execute
    >>> result = await execute(simulation, config, llm_client)
    >>> result.data is None
    True
"""

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient
from src.utils.storage import Simulation


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,  # Unused (phase 3 never uses LLM)
) -> PhaseResult:
    """Apply Master results to simulation state (stub: no-op).

    In real implementation will:
    - Update character locations
    - Update character internal_state, external_intent
    - Add memory_entry to character memory
    - Update location moment/description

    Args:
        simulation: Current simulation state.
        config: Application configuration.
        llm_client: LLM client (unused, phase 3 is pure mechanics).

    Returns:
        PhaseResult with data=None.

    Example:
        >>> result = await execute(sim, config, client)
        >>> result.success
        True
    """
    # Real implementation will:
    # - Update character locations
    # - Update character internal_state, external_intent
    # - Add memory_entry to character memory
    # - Update location moment/description

    return PhaseResult(success=True, data=None)
