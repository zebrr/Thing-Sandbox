"""Unit tests for Phase 1: Character intentions."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Config
from src.phases.phase1 import IntentionResponse, _group_by_location, execute
from src.utils.llm_adapters.base import AdapterResponse, ResponseDebugInfo, ResponseUsage
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


def make_intention_response(intention: str = "I will do something") -> IntentionResponse:
    """Create a test IntentionResponse."""
    return IntentionResponse(intention=intention)


def make_adapter_response(
    intention: str = "Test intention",
    response_id: str = "resp_test",
) -> AdapterResponse[IntentionResponse]:
    """Create AdapterResponse with IntentionResponse."""
    return AdapterResponse(
        response_id=response_id,
        parsed=IntentionResponse(intention=intention),
        usage=ResponseUsage(
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=0,
            cached_tokens=0,
            total_tokens=150,
        ),
        debug=ResponseDebugInfo(
            model="test-model",
            created_at=1234567890,
            service_tier=None,
            reasoning_summary=None,
        ),
    )


# =============================================================================
# IntentionResponse Tests
# =============================================================================


class TestIntentionResponse:
    """Tests for IntentionResponse model."""

    def test_intention_response_creation(self) -> None:
        """IntentionResponse can be created with intention field."""
        response = IntentionResponse(intention="I want to explore")
        assert response.intention == "I want to explore"

    def test_intention_response_unicode(self) -> None:
        """IntentionResponse handles non-ASCII characters."""
        response = IntentionResponse(intention="Хочу исследовать пещеру")
        assert response.intention == "Хочу исследовать пещеру"

    def test_intention_response_empty_string(self) -> None:
        """IntentionResponse accepts empty string."""
        response = IntentionResponse(intention="")
        assert response.intention == ""


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
        ids = [c.identity.id for c in groups["tavern"]]
        assert "alice" in ids
        assert "bob" in ids

    def test_multiple_characters_different_locations(self) -> None:
        """Characters at different locations grouped separately."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "forest")
        characters = {"alice": alice, "bob": bob}

        groups = _group_by_location(characters)

        assert len(groups) == 2
        assert "tavern" in groups
        assert "forest" in groups
        assert len(groups["tavern"]) == 1
        assert len(groups["forest"]) == 1

    def test_empty_characters(self) -> None:
        """Empty characters dict returns empty groups."""
        groups = _group_by_location({})
        assert groups == {}

    def test_mixed_locations(self) -> None:
        """Mix of single and multiple characters per location."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "tavern")
        charlie = make_character("charlie", "Charlie", "forest")
        characters = {"alice": alice, "bob": bob, "charlie": charlie}

        groups = _group_by_location(characters)

        assert len(groups["tavern"]) == 2
        assert len(groups["forest"]) == 1


# =============================================================================
# execute() Tests - Context Building
# =============================================================================


class TestExecuteContextBuilding:
    """Tests for context assembly in execute()."""

    @pytest.mark.asyncio
    async def test_build_context_single_character_alone(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Single character alone in location has empty others list."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [make_intention_response("I will wait")]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client)

            # Check user prompt render call
            user_calls = [
                c for c in mock_renderer.render.call_args_list if c[0][0] == "phase1_intention_user"
            ]
            assert len(user_calls) == 1
            context = user_calls[0][0][1]
            assert context["others"] == []

    @pytest.mark.asyncio
    async def test_build_context_multiple_characters_same_location(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Multiple characters see each other in others list."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice, "bob": bob}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [
            make_intention_response("Alice intention"),
            make_intention_response("Bob intention"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client)

            # Check user prompt render calls
            user_calls = [
                c for c in mock_renderer.render.call_args_list if c[0][0] == "phase1_intention_user"
            ]
            assert len(user_calls) == 2

            # Each character should see the other
            for call in user_calls:
                context = call[0][1]
                char = context["character"]
                others = context["others"]
                # Should have exactly 1 other
                assert len(others) == 1
                # Other should not be self
                assert others[0].identity.id != char.identity.id

    @pytest.mark.asyncio
    async def test_build_context_characters_different_locations(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Characters in different locations don't see each other."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "forest")
        tavern = make_location("tavern", "The Tavern")
        forest = make_location("forest", "Dark Forest")
        sim = make_simulation(
            {"alice": alice, "bob": bob},
            {"tavern": tavern, "forest": forest},
        )

        mock_llm_client.create_batch.return_value = [
            make_intention_response("Alice intention"),
            make_intention_response("Bob intention"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client)

            user_calls = [
                c for c in mock_renderer.render.call_args_list if c[0][0] == "phase1_intention_user"
            ]

            # Both characters should have empty others list
            for call in user_calls:
                context = call[0][1]
                assert context["others"] == []


# =============================================================================
# execute() Tests - Batch Execution
# =============================================================================


class TestExecuteBatchExecution:
    """Tests for batch execution in execute()."""

    @pytest.mark.asyncio
    async def test_execute_all_success(self, config: Config, mock_llm_client: MagicMock) -> None:
        """All characters get intentions on success."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "forest")
        tavern = make_location("tavern", "The Tavern")
        forest = make_location("forest", "Dark Forest")
        sim = make_simulation(
            {"alice": alice, "bob": bob},
            {"tavern": tavern, "forest": forest},
        )

        mock_llm_client.create_batch.return_value = [
            make_intention_response("Alice explores"),
            make_intention_response("Bob waits"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

        assert result.success is True
        assert "alice" in result.data
        assert "bob" in result.data
        assert result.data["alice"].intention == "Alice explores"
        assert result.data["bob"].intention == "Bob waits"

    @pytest.mark.asyncio
    async def test_execute_creates_correct_requests(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Execute creates LLMRequest with correct entity_key."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [make_intention_response()]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client)

        # Check create_batch was called with correct requests
        call_args = mock_llm_client.create_batch.call_args
        requests = call_args[0][0]
        assert len(requests) == 1
        assert requests[0].entity_key == "intention:alice"
        assert requests[0].schema is IntentionResponse

    @pytest.mark.asyncio
    async def test_execute_empty_simulation(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Empty simulation returns empty data."""
        sim = make_simulation({}, {})

        mock_llm_client.create_batch.return_value = []

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

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
        """Partial failure: some success, some fallback to idle."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "forest")
        tavern = make_location("tavern", "The Tavern")
        forest = make_location("forest", "Dark Forest")
        sim = make_simulation(
            {"alice": alice, "bob": bob},
            {"tavern": tavern, "forest": forest},
        )

        # Alice succeeds, Bob fails
        mock_llm_client.create_batch.return_value = [
            make_intention_response("Alice explores"),
            LLMRateLimitError("Rate limit exceeded"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

        assert result.success is True
        assert result.data["alice"].intention == "Alice explores"
        assert result.data["bob"].intention == "idle"

    @pytest.mark.asyncio
    async def test_execute_all_failure_fallback(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """All failures: all characters fallback to idle."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "forest")
        tavern = make_location("tavern", "The Tavern")
        forest = make_location("forest", "Dark Forest")
        sim = make_simulation(
            {"alice": alice, "bob": bob},
            {"tavern": tavern, "forest": forest},
        )

        mock_llm_client.create_batch.return_value = [
            LLMTimeoutError("Timeout"),
            LLMRateLimitError("Rate limit"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

        assert result.success is True
        assert result.data["alice"].intention == "idle"
        assert result.data["bob"].intention == "idle"

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

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            import logging

            with caplog.at_level(logging.WARNING):
                await execute(sim, config, mock_llm_client)

        assert "alice" in caplog.text
        assert "fallback to idle" in caplog.text

    @pytest.mark.asyncio
    async def test_fallback_prints_console(
        self, config: Config, mock_llm_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Fallback prints message to console."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [
            LLMRateLimitError("Rate limit exceeded"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client)

        captured = capsys.readouterr()
        assert "alice" in captured.out
        assert "fallback to idle" in captured.out
        assert "LLMRateLimitError" in captured.out

    @pytest.mark.asyncio
    async def test_execute_invalid_location_fallback(
        self, config: Config, mock_llm_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Character with invalid location falls back to idle immediately."""
        # Alice has valid location, Bob has invalid
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "nonexistent")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice, "bob": bob}, {"tavern": tavern})

        # Only one request (for Alice), Bob skipped
        mock_llm_client.create_batch.return_value = [
            make_intention_response("Alice explores"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

        # Both characters should be in result
        assert result.success is True
        assert "alice" in result.data
        assert "bob" in result.data

        # Alice got LLM result, Bob got fallback
        assert result.data["alice"].intention == "Alice explores"
        assert result.data["bob"].intention == "idle"

        # Console message for Bob
        captured = capsys.readouterr()
        assert "bob" in captured.out
        assert "invalid location" in captured.out

        # Only one LLM request was made (for Alice)
        call_args = mock_llm_client.create_batch.call_args
        requests = call_args[0][0]
        assert len(requests) == 1
        assert requests[0].entity_key == "intention:alice"

    @pytest.mark.asyncio
    async def test_execute_all_invalid_locations_no_batch(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """If all characters have invalid locations, no batch is executed."""
        alice = make_character("alice", "Alice", "nowhere")
        bob = make_character("bob", "Bob", "void")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice, "bob": bob}, {"tavern": tavern})

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

        # Both fallback to idle
        assert result.success is True
        assert result.data["alice"].intention == "idle"
        assert result.data["bob"].intention == "idle"

        # No batch was called
        mock_llm_client.create_batch.assert_not_called()


# =============================================================================
# execute() Tests - Result Structure
# =============================================================================


class TestExecuteResultStructure:
    """Tests for result structure of execute()."""

    @pytest.mark.asyncio
    async def test_result_has_all_characters(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Result contains entry for every character."""
        alice = make_character("alice", "Alice", "tavern")
        bob = make_character("bob", "Bob", "tavern")
        charlie = make_character("charlie", "Charlie", "forest")
        tavern = make_location("tavern", "The Tavern")
        forest = make_location("forest", "Dark Forest")
        sim = make_simulation(
            {"alice": alice, "bob": bob, "charlie": charlie},
            {"tavern": tavern, "forest": forest},
        )

        mock_llm_client.create_batch.return_value = [
            make_intention_response("A"),
            make_intention_response("B"),
            make_intention_response("C"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

        assert len(result.data) == 3
        assert "alice" in result.data
        assert "bob" in result.data
        assert "charlie" in result.data

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

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_result_data_contains_intention_response(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """Result data values are IntentionResponse instances."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [
            make_intention_response("Test"),
        ]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            result = await execute(sim, config, mock_llm_client)

        assert isinstance(result.data["alice"], IntentionResponse)


# =============================================================================
# execute() Tests - Prompt Rendering
# =============================================================================


class TestExecutePromptRendering:
    """Tests for prompt rendering in execute()."""

    @pytest.mark.asyncio
    async def test_render_system_prompt_no_variables(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """System prompt rendered with empty context."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [make_intention_response()]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client)

            system_calls = [
                c
                for c in mock_renderer.render.call_args_list
                if c[0][0] == "phase1_intention_system"
            ]
            assert len(system_calls) == 1
            assert system_calls[0][0][1] == {}

    @pytest.mark.asyncio
    async def test_render_user_prompt_with_context(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """User prompt rendered with character, location, others."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern})

        mock_llm_client.create_batch.return_value = [make_intention_response()]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client)

            user_calls = [
                c for c in mock_renderer.render.call_args_list if c[0][0] == "phase1_intention_user"
            ]
            assert len(user_calls) == 1
            context = user_calls[0][0][1]
            assert "character" in context
            assert "location" in context
            assert "others" in context
            assert context["character"].identity.id == "alice"
            assert context["location"].identity.id == "tavern"

    @pytest.mark.asyncio
    async def test_renderer_uses_simulation_path(
        self, config: Config, mock_llm_client: MagicMock
    ) -> None:
        """PromptRenderer initialized with correct simulation path."""
        alice = make_character("alice", "Alice", "tavern")
        tavern = make_location("tavern", "The Tavern")
        sim = make_simulation({"alice": alice}, {"tavern": tavern}, sim_id="my-sim")

        mock_llm_client.create_batch.return_value = [make_intention_response()]

        with patch("src.phases.phase1.PromptRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer.render.return_value = "rendered prompt"
            mock_renderer_class.return_value = mock_renderer

            await execute(sim, config, mock_llm_client)

            # Check PromptRenderer was initialized with correct sim_path
            init_kwargs = mock_renderer_class.call_args.kwargs
            assert "sim_path" in init_kwargs
            assert str(init_kwargs["sim_path"]).endswith("my-sim")
