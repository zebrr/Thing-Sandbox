"""Phase 4: Memory update (STUB).

Performs FIFO shift of memory cells and summarization of evicted entries.
This stub is a no-op.

Example:
    >>> from src.phases.phase4 import execute
    >>> result = await execute(simulation, config, llm_client, {"bob": "I saw..."})
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
    llm_client: LLMClient,  # Unused in stub
    pending_memories: dict[str, str],  # char_id -> memory_entry
) -> PhaseResult:
    """Update character memories (stub: no-op).

    In real implementation will:
    - FIFO shift memory cells
    - Summarize evicted cell into summary (LLM call)
    - Add new memory_entry from pending_memories to cell 0

    Args:
        simulation: Current simulation state.
        config: Application configuration.
        llm_client: LLM client for summarization calls (unused in stub).
        pending_memories: Mapping char_id -> memory_entry from Phase 3.

    Returns:
        PhaseResult with data=None.

    Example:
        >>> result = await execute(sim, config, client, {"bob": "I saw..."})
        >>> result.success
        True
    """
    # Real implementation will use pending_memories
    _ = pending_memories  # Silence unused warning

    return PhaseResult(success=True, data=None)
