"""Unit tests for Phase 2a: Scene arbitration."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.config import Config
from src.phases.phase2a import (
    CharacterUpdate,
    LocationUpdate,
    MasterOutput,
    _create_fallback,
    _group_by_location,
    execute,
)
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


# =============================================================================
# Pydantic Models Tests
# =============================================================================


class TestCharacterUpdate:
    """Tests for CharacterUpdate model."""

    def test_character_update_creation(self) -> None:
        """CharacterUpdate can be created with all fields."""
        update = CharacterUpdate(
            character_id="bob",
            location="forest",
            internal_state="Tired",
            external_intent="Rest",
            memory_entry="I walked to the forest.",
        )
        assert update.character_id == "bob"
        assert update.location == "forest"
        assert update.internal_state == "Tired"
        assert update.external_intent == "Rest"
        assert update.memory_entry == "I walked to the forest."

    def test_character_update_memory_entry_required(self) -> None:
        """CharacterUpdate requires non-empty memory_entry."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            CharacterUpdate(
                character_id="bob",
                location="tavern",
                internal_state="Fine",
                external_intent="Wait",
                memory_entry="",
            )

    def test_character_update_unicode(self) -> None:
        """CharacterUpdate handles non-ASCII characters."""
        update = CharacterUpdate(
            character_id="борис",
            location="таверна",
            internal_state="Устал",
            external_intent="Отдохнуть",
            memory_entry="Я дошёл до леса.",
        )
        assert update.memory_entry == "Я дошёл до леса."


class TestLocationUpdate:
    """Tests for LocationUpdate model."""

    def test_location_update_optional_fields(self) -> None:
        """LocationUpdate has optional moment and description."""
        update = LocationUpdate()
        assert update.moment is None
        assert update.description is None

    def test_location_update_with_values(self) -> None:
        """LocationUpdate can have values."""
        update = LocationUpdate(moment="Evening falls", description="The tavern is now empty")
        assert update.moment == "Evening falls"
        assert update.description == "The tavern is now empty"


class TestMasterOutput:
    """Tests for MasterOutput model."""

    def test_master_output_creation(self) -> None:
        """MasterOutput can be created with all fields."""
        output = MasterOutput(
            tick=5,
            location_id="tavern",
            characters=[
                CharacterUpdate(
                    character_id="bob",
                    location="tavern",
                    internal_state="Happy",
                    external_intent="Drink",
                    memory_entry="I had a drink.",
                )
            ],
            location=LocationUpdate(moment="Night"),
        )
        assert output.tick == 5
        assert output.location_id == "tavern"
        assert len(output.characters) == 1
        assert "bob" in output.characters_dict
        assert output.location.moment == "Night"

    def test_master_output_empty_characters(self) -> None:
        """MasterOutput can have empty characters list (empty location)."""
        output = MasterOutput(
            tick=0,
            location_id="forest",
            characters=[],
            location=LocationUpdate(),
        )
        assert output.characters == []
        assert output.characters_dict == {}


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

    def test_multiple_characters_different_locations(self) -> None:
        """Characters at different locations grouped separately."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "forest")
        characters = {"alice": alice, "bob": bob}

        groups = _group_by_location(characters)

        assert len(groups) == 2
        assert "tavern" in groups
        assert "forest" in groups


# =============================================================================
# _create_fallback Tests
# =============================================================================


class TestCreateFallback:
    """Tests for _create_fallback helper."""

    def test_fallback_preserves_location(self) -> None:
        """Fallback keeps characters in their current location."""
        alice = make_character("alice", "Alice", "tavern")
        sim = make_simulation({"alice": alice}, {"tavern": make_location("tavern", "Tavern")})

        fallback = _create_fallback(sim, "tavern", {"alice": alice})

        assert fallback.characters_dict["alice"].location == "tavern"

    def test_fallback_preserves_state(self) -> None:
        """Fallback keeps current internal_state and external_intent."""
        alice = make_character(
            "alice", "Alice", "tavern", internal_state="Happy", external_intent="Wait"
        )
        sim = make_simulation({"alice": alice}, {"tavern": make_location("tavern", "Tavern")})

        fallback = _create_fallback(sim, "tavern", {"alice": alice})

        assert fallback.characters_dict["alice"].internal_state == "Happy"
        assert fallback.characters_dict["alice"].external_intent == "Wait"

    def test_fallback_uses_placeholder_memory(self) -> None:
        """Fallback uses placeholder memory entry."""
        alice = make_character("alice", "Alice", "tavern")
        sim = make_simulation({"alice": alice}, {"tavern": make_location("tavern", "Tavern")})

        fallback = _create_fallback(sim, "tavern", {"alice": alice})

        assert "[No resolution" in fallback.characters_dict["alice"].memory_entry

    def test_fallback_null_location_updates(self) -> None:
        """Fallback has null location updates."""
        alice = make_character("alice", "Alice", "tavern")
        sim = make_simulation({"alice": alice}, {"tavern": make_location("tavern", "Tavern")})

        fallback = _create_fallback(sim, "tavern", {"alice": alice})

        assert fallback.location.moment is None
        assert fallback.location.description is None


# =============================================================================
# execute() Tests - Context Building
# =============================================================================


class TestExecuteContextBuilding:
    """Tests for context assembly in execute()."""

    @pytest.mark.asyncio
    async def test_context_includes_simulation(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Context includes simulation for current_tick."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [make_master_output()]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, {"alice": "explore"})

            user_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase2a_resolution_user"
            ]
            assert len(user_calls) == 1
            context = user_calls[0][0][1]
            assert "simulation" in context
            assert context["simulation"].current_tick == 0

    @pytest.mark.asyncio
    async def test_context_includes_intentions(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Context includes intentions for characters in location."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice, "bob": bob}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [make_master_output()]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, {"alice": "explore", "bob": "wait"})

            user_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase2a_resolution_user"
            ]
            context = user_calls[0][0][1]
            assert "intentions" in context
            assert context["intentions"]["alice"] == "explore"
            assert context["intentions"]["bob"] == "wait"

    @pytest.mark.asyncio
    async def test_empty_location_no_characters(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Empty location has no characters in context."""
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [make_master_output()]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, {})

            user_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase2a_resolution_user"
            ]
            context = user_calls[0][0][1]
            assert context["characters"] == []
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

        expected = make_master_output(
            location_id="tavern",
            characters=[make_character_update(character_id="alice")],
        )
        mock_llm_client.create_batch.return_value = [expected]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, {"alice": "explore"})

        assert result.success is True
        assert "tavern" in result.data
        assert result.data["tavern"].location_id == "tavern"

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

        mock_llm_client.create_batch.return_value = [
            make_master_output(location_id="tavern"),
            make_master_output(location_id="forest"),
        ]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, {"alice": "explore", "bob": "wait"}
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

        mock_llm_client.create_batch.return_value = [make_master_output()]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client, {"alice": "explore"})

        call_args = mock_llm_client.create_batch.call_args
        requests = call_args[0][0]
        assert len(requests) == 1
        assert requests[0].entity_key == "resolution:tavern"
        assert requests[0].schema is MasterOutput


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

        # Tavern succeeds, forest fails
        mock_llm_client.create_batch.return_value = [
            make_master_output(location_id="tavern"),
            LLMRateLimitError("Rate limit exceeded"),
        ]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(
                sim, config, mock_llm_client, {"alice": "explore", "bob": "wait"}
            )

        assert result.success is True
        assert "tavern" in result.data
        assert "forest" in result.data
        # Forest should have fallback
        assert "[No resolution" in result.data["forest"].characters_dict["bob"].memory_entry

    @pytest.mark.asyncio
    async def test_execute_all_failure_fallback(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """All failures: all locations get fallback."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [
            LLMTimeoutError("Timeout"),
        ]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, {"alice": "explore"})

        assert result.success is True
        assert "[No resolution" in result.data["tavern"].characters_dict["alice"].memory_entry

    @pytest.mark.asyncio
    async def test_fallback_logs_warning(
        self, config: Config, mock_llm_client: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Fallback logs warning message."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [
            LLMRateLimitError("Rate limit exceeded"),
        ]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            import logging

            with caplog.at_level(logging.WARNING):
                await execute(sim, config, mock_llm_client, {"alice": "explore"})

        assert "tavern" in caplog.text
        assert "fallback" in caplog.text


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

        mock_llm_client.create_batch.return_value = [
            make_master_output(location_id="tavern"),
            make_master_output(location_id="forest"),
        ]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, {"alice": "explore"})

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

        mock_llm_client.create_batch.return_value = [
            LLMError("Generic error"),
        ]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, {"alice": "explore"})

        assert result.success is True

    @pytest.mark.asyncio
    async def test_result_data_contains_master_output(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Result data values are MasterOutput instances."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [
            make_master_output(location_id="tavern"),
        ]

        with patch("src.phases.phase2a.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client, {"alice": "explore"})

        assert isinstance(result.data["tavern"], MasterOutput)
