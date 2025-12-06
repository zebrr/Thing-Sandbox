"""Unit tests for Phase 2b: Narrative generation."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.config import Config
from src.phases.phase2a import CharacterUpdate, LocationUpdate, MasterOutput
from src.phases.phase2b import NarrativeResponse, _group_by_location, execute
from src.utils.llm_errors import LLMError, LLMRateLimitError, LLMTimeoutError
from src.utils.storage import (
    Character,
    CharacterIdentity,
    CharacterMemory,
    CharacterState,
    Location,
    LocationConnection,
    LocationIdentity,
    LocationState,
    Simulation,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config() -> Config:
    """Load config."""
    return Config.load()


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Create mock LLM client."""
    client = MagicMock()
    client.create_batch = AsyncMock()
    return client


def make_character(
    char_id: str,
    name: str,
    location: str,
    description: str = "A test character",
    internal_state: str | None = None,
    external_intent: str | None = None,
) -> Character:
    """Create a test character."""
    return Character(
        identity=CharacterIdentity(
            id=char_id,
            name=name,
            description=description,
        ),
        state=CharacterState(
            location=location,
            internal_state=internal_state,
            external_intent=external_intent,
        ),
        memory=CharacterMemory(),
    )


def make_location(
    loc_id: str,
    name: str,
    description: str = "A test location",
    moment: str = "Nothing special happening",
    connections: list[LocationConnection] | None = None,
) -> Location:
    """Create a test location."""
    return Location(
        identity=LocationIdentity(
            id=loc_id,
            name=name,
            description=description,
            connections=connections or [],
        ),
        state=LocationState(moment=moment),
    )


def make_simulation(
    characters: dict[str, Character],
    locations: dict[str, Location],
    sim_id: str = "test-sim",
) -> Simulation:
    """Create a test simulation."""
    return Simulation(
        id=sim_id,
        current_tick=0,
        created_at=datetime.now(),
        status="paused",
        characters=characters,
        locations=locations,
    )


def make_master_output(
    tick: int = 0,
    location_id: str = "tavern",
    characters: list[CharacterUpdate] | None = None,
    location: LocationUpdate | None = None,
) -> MasterOutput:
    """Create a test MasterOutput."""
    return MasterOutput(
        tick=tick,
        location_id=location_id,
        characters=characters or [],
        location=location or LocationUpdate(),
    )


def make_character_update(
    character_id: str = "test_char",
    location: str = "tavern",
    internal_state: str = "Fine",
    external_intent: str = "Waiting",
    memory_entry: str = "Nothing happened.",
) -> CharacterUpdate:
    """Create a test CharacterUpdate."""
    return CharacterUpdate(
        character_id=character_id,
        location=location,
        internal_state=internal_state,
        external_intent=external_intent,
        memory_entry=memory_entry,
    )


def make_narrative_response(narrative: str = "The sun set over the hills.") -> NarrativeResponse:
    """Create a test NarrativeResponse."""
    return NarrativeResponse(narrative=narrative)


# =============================================================================
# NarrativeResponse Tests
# =============================================================================


class TestNarrativeResponse:
    """Tests for NarrativeResponse model."""

    def test_narrative_response_creation(self) -> None:
        """NarrativeResponse can be created with narrative field."""
        response = NarrativeResponse(narrative="The morning sun rose.")
        assert response.narrative == "The morning sun rose."

    def test_narrative_response_min_length(self) -> None:
        """NarrativeResponse rejects empty string (min_length=1)."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            NarrativeResponse(narrative="")

    def test_narrative_response_unicode(self) -> None:
        """NarrativeResponse handles non-ASCII characters."""
        response = NarrativeResponse(narrative="Солнце взошло над холмами.")
        assert response.narrative == "Солнце взошло над холмами."


# =============================================================================
# _group_by_location Tests
# =============================================================================


class TestGroupByLocation:
    """Tests for _group_by_location helper."""

    def test_single_character_single_location(self) -> None:
        """Single character grouped correctly."""
        alice = make_character("alice", "Alice", "tavern")
        characters = {"alice": alice}

        groups = _group_by_location(characters)

        assert "tavern" in groups
        assert len(groups["tavern"]) == 1
        assert groups["tavern"][0].identity.id == "alice"

    def test_multiple_characters_same_location(self) -> None:
        """Multiple characters at same location grouped together."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "tavern")
        characters = {"alice": alice, "bob": bob}

        groups = _group_by_location(characters)

        assert "tavern" in groups
        assert len(groups["tavern"]) == 2


# =============================================================================
# execute() Tests - Context Building
# =============================================================================


class TestExecuteContextBuilding:
    """Tests for context assembly in execute()."""

    @pytest.mark.asyncio
    async def test_context_includes_location_before(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Context includes location_before."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern", moment="Evening")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [make_narrative_response()]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, master_results, {"alice": "explore"})

            user_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase2b_narrative_user"
            ]
            assert len(user_calls) == 1
            context = user_calls[0][0][1]
            assert "location_before" in context
            assert context["location_before"].state.moment == "Evening"

    @pytest.mark.asyncio
    async def test_context_includes_characters_before(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Context includes characters_before."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice, "bob": bob}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [make_narrative_response()]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(
                sim, config, mock_llm_client, master_results, {"alice": "explore", "bob": "wait"}
            )

            user_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase2b_narrative_user"
            ]
            context = user_calls[0][0][1]
            assert "characters_before" in context
            assert len(context["characters_before"]) == 2

    @pytest.mark.asyncio
    async def test_context_includes_master_result(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Context includes master_result."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {
            "tavern": make_master_output(
                location_id="tavern",
                location=LocationUpdate(moment="Night falls"),
            )
        }

        mock_llm_client.create_batch.return_value = [make_narrative_response()]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, master_results, {"alice": "explore"})

            user_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase2b_narrative_user"
            ]
            context = user_calls[0][0][1]
            assert "master_result" in context
            assert context["master_result"].location.moment == "Night falls"

    @pytest.mark.asyncio
    async def test_context_includes_intentions(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Context includes intentions for characters."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [make_narrative_response()]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, master_results, {"alice": "explore"})

            user_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase2b_narrative_user"
            ]
            context = user_calls[0][0][1]
            assert "intentions" in context
            assert context["intentions"]["alice"] == "explore"

    @pytest.mark.asyncio
    async def test_empty_location_no_characters(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Empty location has no characters_before."""
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [make_narrative_response()]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, master_results, {})

            user_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase2b_narrative_user"
            ]
            context = user_calls[0][0][1]
            assert context["characters_before"] == []
            assert context["intentions"] == {}


# =============================================================================
# execute() Tests - Batch Execution
# =============================================================================


class TestExecuteBatchExecution:
    """Tests for batch execution in execute()."""

    @pytest.mark.asyncio
    async def test_execute_single_location(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Single location produces single request."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        expected = make_narrative_response("Alice entered the tavern.")
        mock_llm_client.create_batch.return_value = [expected]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, master_results, {"alice": "enter"})

        assert result.success is True
        assert "tavern" in result.data
        assert result.data["tavern"].narrative == "Alice entered the tavern."

    @pytest.mark.asyncio
    async def test_execute_multiple_locations(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Multiple locations produce multiple requests."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "forest")
        tavern = make_location("tavern", "The Tavern")
        forest = make_location("forest", "Dark Forest")
        sim = make_simulation({"alice": alice, "bob": bob}, {"tavern": tavern, "forest": forest})
        master_results = {
            "tavern": make_master_output(location_id="tavern"),
            "forest": make_master_output(location_id="forest"),
        }

        mock_llm_client.create_batch.return_value = [
            make_narrative_response("Tavern story."),
            make_narrative_response("Forest story."),
        ]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, master_results, {"alice": "wait", "bob": "explore"}
            )

        assert len(result.data) == 2
        assert "tavern" in result.data
        assert "forest" in result.data

    @pytest.mark.asyncio
    async def test_execute_creates_correct_entity_key(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Execute creates LLMRequest with correct entity_key format."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [make_narrative_response()]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, master_results, {"alice": "explore"})

        call_args = mock_llm_client.create_batch.call_args
        requests = call_args[0][0]
        assert len(requests) == 1
        assert requests[0].entity_key == "narrative:tavern"
        assert requests[0].schema is NarrativeResponse

    @pytest.mark.asyncio
    async def test_execute_empty_simulation(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Empty simulation (no locations) returns empty data."""
        sim = make_simulation({}, {})

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, {}, {})

        assert result.success is True
        assert result.data == {}


# =============================================================================
# execute() Tests - Fallback Handling
# =============================================================================


class TestExecuteFallback:
    """Tests for fallback handling in execute()."""

    @pytest.mark.asyncio
    async def test_execute_partial_failure_fallback(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Partial failure: some success, some fallback."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "forest")
        tavern = make_location("tavern", "The Tavern")
        forest = make_location("forest", "Dark Forest")
        sim = make_simulation({"alice": alice, "bob": bob}, {"tavern": tavern, "forest": forest})
        master_results = {
            "tavern": make_master_output(location_id="tavern"),
            "forest": make_master_output(location_id="forest"),
        }

        # Tavern succeeds, forest fails
        mock_llm_client.create_batch.return_value = [
            make_narrative_response("Tavern story."),
            LLMRateLimitError("Rate limit exceeded"),
        ]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, master_results, {"alice": "wait", "bob": "explore"}
            )

        assert result.success is True
        assert result.data["tavern"].narrative == "Tavern story."
        assert "[Silence" in result.data["forest"].narrative

    @pytest.mark.asyncio
    async def test_execute_all_failure_fallback(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """All failures: all locations get fallback."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [
            LLMTimeoutError("Timeout"),
        ]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, master_results, {"alice": "explore"}
            )

        assert result.success is True
        assert "[Silence" in result.data["tavern"].narrative

    @pytest.mark.asyncio
    async def test_fallback_logs_warning(
        self, config: Config, mock_llm_client: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Fallback logs warning message."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [
            LLMRateLimitError("Rate limit exceeded"),
        ]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            import logging

            with caplog.at_level(logging.WARNING):
                await execute(sim, config, mock_llm_client, master_results, {"alice": "explore"})

        assert "tavern" in caplog.text
        assert "fallback" in caplog.text

    @pytest.mark.asyncio
    async def test_fallback_text_is_bracketed(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Fallback narrative uses bracketed placeholder text."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [
            LLMError("Error"),
        ]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, master_results, {"alice": "explore"}
            )

        # Bracketed to indicate technical failure
        assert result.data["tavern"].narrative.startswith("[")
        assert result.data["tavern"].narrative.endswith("]")


# =============================================================================
# execute() Tests - Result Structure
# =============================================================================


class TestExecuteResultStructure:
    """Tests for result structure of execute()."""

    @pytest.mark.asyncio
    async def test_result_has_all_locations(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Result contains entry for every location."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        forest = make_location("forest", "Dark Forest")
        sim = make_simulation({"alice": alice}, {"tavern": tavern, "forest": forest})
        master_results = {
            "tavern": make_master_output(location_id="tavern"),
            "forest": make_master_output(location_id="forest"),
        }

        mock_llm_client.create_batch.return_value = [
            make_narrative_response("Tavern."),
            make_narrative_response("Forest."),
        ]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, master_results, {"alice": "explore"}
            )

        assert len(result.data) == 2
        assert "tavern" in result.data
        assert "forest" in result.data

    @pytest.mark.asyncio
    async def test_result_success_always_true(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Result success is True even with all fallbacks."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [
            LLMError("Generic error"),
        ]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, master_results, {"alice": "explore"}
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_result_data_contains_narrative_response(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Result data values are NarrativeResponse instances."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        master_results = {"tavern": make_master_output(location_id="tavern")}

        mock_llm_client.create_batch.return_value = [
            make_narrative_response("Test."),
        ]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, master_results, {"alice": "explore"}
            )

        assert isinstance(result.data["tavern"], NarrativeResponse)


# =============================================================================
# execute() Tests - Missing MasterOutput
# =============================================================================


class TestExecuteMissingMasterOutput:
    """Tests for handling missing MasterOutput."""

    @pytest.mark.asyncio
    async def test_missing_master_result_logs_warning(
        self, config: Config, mock_llm_client: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing MasterOutput logs warning."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})
        # Empty master_results - no result for tavern
        master_results: dict[str, MasterOutput] = {}

        mock_llm_client.create_batch.return_value = [make_narrative_response()]

        with patch("src.phases.phase2b.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            import logging

            with caplog.at_level(logging.WARNING):
                await execute(sim, config, mock_llm_client, master_results, {"alice": "explore"})

        assert "missing MasterOutput" in caplog.text
        assert "tavern" in caplog.text
