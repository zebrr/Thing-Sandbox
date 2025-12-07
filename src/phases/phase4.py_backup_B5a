"""Phase 4: Memory update.

Performs FIFO shift of memory cells and summarization of evicted entries.
When memory queue is full (K cells), oldest cell is summarized into compressed
history before adding new memory. Uses LLM for summarization with graceful
fallback on errors.

Example:
    >>> from src.phases.phase4 import execute, SummaryResponse
    >>> result = await execute(simulation, config, llm_client, {"bob": "I saw..."})
    >>> result.success
    True
    >>> result.data is None  # Updates applied in-place
    True
"""

import logging

from pydantic import BaseModel, Field

from src.config import Config
from src.phases.common import PhaseResult
from src.utils.llm import LLMClient, LLMRequest
from src.utils.llm_errors import LLMError
from src.utils.prompts import PromptRenderer
from src.utils.storage import Character, MemoryCell, Simulation

logger = logging.getLogger(__name__)


class SummaryResponse(BaseModel):
    """LLM structured output for memory summarization.

    Corresponds to src/schemas/SummaryResponse.schema.json.

    Example:
        >>> response = SummaryResponse(summary="I remember meeting the stranger...")
        >>> response.summary
        'I remember meeting the stranger...'
    """

    summary: str = Field(..., min_length=1)


def _partition_characters(
    characters: dict[str, Character],
    pending_memories: dict[str, str],
    max_cells: int,
) -> tuple[list[Character], list[Character]]:
    """Partition characters by whether they need summarization.

    Characters with full memory queues (len(cells) >= max_cells) need LLM
    summarization before adding new memory. Characters with space can
    add memory directly.

    Args:
        characters: All characters in simulation.
        pending_memories: Mapping char_id -> memory_entry from Phase 3.
        max_cells: Maximum memory cells before summarization needed (K).

    Returns:
        Tuple of (needs_summary, has_space) - two lists of characters.

    Example:
        >>> needs, has_space = _partition_characters(chars, pending, 5)
        >>> len(needs)  # Characters with full memory
        2
    """
    needs_summary: list[Character] = []
    has_space: list[Character] = []

    for char_id, char in characters.items():
        if char_id not in pending_memories:
            continue  # No memory to add for this character

        if len(char.memory.cells) >= max_cells:
            needs_summary.append(char)
        else:
            has_space.append(char)

    return needs_summary, has_space


def _add_memory_cell(character: Character, tick: int, text: str) -> None:
    """Insert new memory cell at front of queue.

    Args:
        character: Character to update.
        tick: Tick number for the new memory.
        text: Memory text content.

    Example:
        >>> _add_memory_cell(char, 5, "I saw a dragon")
        >>> char.memory.cells[0].text
        'I saw a dragon'
    """
    new_cell = MemoryCell(tick=tick, text=text)
    character.memory.cells.insert(0, new_cell)


async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
    pending_memories: dict[str, str],
) -> PhaseResult:
    """Update character memories with FIFO queue and summarization.

    For each character with pending memory:
    1. If queue is full (len(cells) >= K):
       - Call LLM to merge old_summary + oldest_cell into new_summary
       - On success: update summary, remove oldest cell, add new cell
       - On error: skip character entirely (fallback - memory unchanged)
    2. If queue has space (len(cells) < K):
       - Just add new cell at front (no LLM needed)

    Args:
        simulation: Current simulation state with characters.
        config: Application configuration (includes memory_cells setting).
        llm_client: LLM client for summarization calls.
        pending_memories: Mapping char_id -> memory_entry from Phase 3.

    Returns:
        PhaseResult with success=True and data=None.
        Memory updates are applied in-place to simulation.characters.

    Example:
        >>> result = await execute(sim, config, client, {"bob": "I saw..."})
        >>> result.success
        True
    """
    # Get K from config
    max_cells = config.simulation.memory_cells

    # Create PromptRenderer with simulation path for override resolution
    sim_path = config.project_root / "simulations" / simulation.id
    renderer = PromptRenderer(config, sim_path=sim_path)

    # Partition characters into those needing summarization and those with space
    needs_summary, has_space = _partition_characters(
        simulation.characters, pending_memories, max_cells
    )

    # Build LLM requests for characters needing summarization
    requests: list[LLMRequest] = []
    for char in needs_summary:
        system_prompt = renderer.render("phase4_summary_system", {})
        user_prompt = renderer.render(
            "phase4_summary_user",
            {
                "character": char,
                "simulation": simulation,
            },
        )

        requests.append(
            LLMRequest(
                instructions=system_prompt,
                input_data=user_prompt,
                schema=SummaryResponse,
                entity_key=f"memory:{char.identity.id}",
            )
        )

    # Execute batch for characters needing summarization
    if requests:
        results = await llm_client.create_batch(requests)

        # Process summarization results with fallback
        for char, result in zip(needs_summary, results):
            char_id = char.identity.id

            if isinstance(result, LLMError):
                error_type = type(result).__name__
                logger.warning(
                    "Phase 4: %s fallback - memory unchanged (%s: %s)",
                    char_id,
                    error_type,
                    result,
                )
                continue  # Skip this character entirely

            # Success: update memory (result is SummaryResponse after LLMError check)
            summary_result: SummaryResponse = result  # type: ignore[assignment]
            char.memory.summary = summary_result.summary
            char.memory.cells.pop()  # Remove oldest cell
            _add_memory_cell(char, simulation.current_tick, pending_memories[char_id])

    # Process characters with space (no LLM needed)
    for char in has_space:
        char_id = char.identity.id
        _add_memory_cell(char, simulation.current_tick, pending_memories[char_id])

    return PhaseResult(success=True, data=None)
