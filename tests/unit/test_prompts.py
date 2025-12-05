"""Unit tests for prompts module."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from src.config import Config, PromptNotFoundError
from src.utils.prompts import PromptRenderer, PromptRenderError

# =============================================================================
# Test Fixtures
# =============================================================================


def make_minimal_config_toml() -> str:
    """Generate minimal valid config.toml content."""
    return """[simulation]

[phase1]
model = "test-model"

[phase2a]
model = "test-model"

[phase2b]
model = "test-model"

[phase4]
model = "test-model"
"""


@pytest.fixture
def config_setup(tmp_path: Path) -> tuple[Config, Path]:
    """Create Config with temporary project structure."""
    # Create config.toml
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")

    # Create pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

    # Create prompts directory
    prompts_dir = tmp_path / "src" / "prompts"
    prompts_dir.mkdir(parents=True)

    config = Config.load(config_path=config_toml, project_root=tmp_path)
    return config, tmp_path


# =============================================================================
# Test Models for Pydantic
# =============================================================================


class MockIdentity(BaseModel):
    """Mock identity for testing nested access."""

    id: str
    name: str
    description: str
    triggers: str | None = None


class MockMemoryCell(BaseModel):
    """Mock memory cell for testing."""

    tick: int
    text: str


class MockMemory(BaseModel):
    """Mock memory for testing."""

    cells: list[MockMemoryCell] = []
    summary: str = ""


class MockState(BaseModel):
    """Mock state for testing."""

    location: str
    internal_state: str | None = None
    external_intent: str | None = None


class MockCharacter(BaseModel):
    """Mock character for testing Pydantic model access."""

    identity: MockIdentity
    state: MockState
    memory: MockMemory


class MockConnection(BaseModel):
    """Mock connection for testing."""

    location_id: str
    description: str


class MockLocationIdentity(BaseModel):
    """Mock location identity for testing."""

    id: str
    name: str
    description: str
    connections: list[MockConnection] = []


class MockLocationState(BaseModel):
    """Mock location state for testing."""

    moment: str = ""


class MockLocation(BaseModel):
    """Mock location for testing."""

    identity: MockLocationIdentity
    state: MockLocationState


# =============================================================================
# Basic Rendering Tests
# =============================================================================


class TestRenderValidContext:
    """Tests for rendering with valid context."""

    def test_render_valid_context(self, config_setup: tuple[Config, Path]) -> None:
        """Renders template with all required variables."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        # Create template with variable
        template = prompts_dir / "test_template.md"
        template.write_text("Hello, {{ name }}!\n", encoding="utf-8")

        renderer = PromptRenderer(config)
        result = renderer.render("test_template", {"name": "Мир"})

        assert result == "Hello, Мир!\n"

    def test_render_empty_context(self, config_setup: tuple[Config, Path]) -> None:
        """Renders template with no variables (system prompts)."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        # Create template without variables
        template = prompts_dir / "system_prompt.md"
        template.write_text("# System Prompt\n\nYou are a helpful assistant.\n", encoding="utf-8")

        renderer = PromptRenderer(config)
        result = renderer.render("system_prompt", {})

        assert result == "# System Prompt\n\nYou are a helpful assistant.\n"

    def test_render_with_pydantic_model(self, config_setup: tuple[Config, Path]) -> None:
        """Pydantic models work as context values."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        # Create template accessing Pydantic model
        template = prompts_dir / "character_prompt.md"
        template.write_text(
            "Name: {{ character.identity.name }}\nLocation: {{ character.state.location }}\n",
            encoding="utf-8",
        )

        character = MockCharacter(
            identity=MockIdentity(
                id="alice",
                name="Алиса",
                description="A curious girl",
            ),
            state=MockState(location="wonderland"),
            memory=MockMemory(),
        )

        renderer = PromptRenderer(config)
        result = renderer.render("character_prompt", {"character": character})

        assert "Name: Алиса" in result
        assert "Location: wonderland" in result


# =============================================================================
# Jinja2 Features Tests
# =============================================================================


class TestJinja2Features:
    """Tests for Jinja2 template features."""

    def test_render_with_default_filter(self, config_setup: tuple[Config, Path]) -> None:
        """Default filter works correctly."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "default_filter.md"
        template.write_text(
            "Triggers: {{ triggers | default('No triggers defined') }}\n",
            encoding="utf-8",
        )

        renderer = PromptRenderer(config)

        # Without value
        result = renderer.render("default_filter", {})
        assert result == "Triggers: No triggers defined\n"

        # With value
        result = renderer.render("default_filter", {"triggers": "Be cautious"})
        assert result == "Triggers: Be cautious\n"

    def test_render_with_loops(self, config_setup: tuple[Config, Path]) -> None:
        """For loop iteration works."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "loop_template.md"
        template.write_text(
            "Items:\n{% for item in items %}- {{ item }}\n{% endfor %}",
            encoding="utf-8",
        )

        renderer = PromptRenderer(config)
        result = renderer.render("loop_template", {"items": ["яблоко", "банан", "вишня"]})

        assert "- яблоко" in result
        assert "- банан" in result
        assert "- вишня" in result

    def test_render_with_conditionals(self, config_setup: tuple[Config, Path]) -> None:
        """If conditions work."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "conditional_template.md"
        template.write_text(
            "{% if show_secret %}Secret: тайна{% else %}No secret{% endif %}\n",
            encoding="utf-8",
        )

        renderer = PromptRenderer(config)

        # Condition true
        result = renderer.render("conditional_template", {"show_secret": True})
        assert "Secret: тайна" in result

        # Condition false
        result = renderer.render("conditional_template", {"show_secret": False})
        assert "No secret" in result

    def test_render_nested_model_access(self, config_setup: tuple[Config, Path]) -> None:
        """Deep attribute access works (character.identity.name)."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "nested_access.md"
        template.write_text(
            "Character: {{ character.identity.name }}\n"
            "Memory summary: {{ character.memory.summary | default('Empty') }}\n"
            "Triggers: {{ character.identity.triggers | default('None') }}\n",
            encoding="utf-8",
        )

        character = MockCharacter(
            identity=MockIdentity(
                id="bob",
                name="Боб",
                description="A wizard",
                triggers="Cast spells when threatened",
            ),
            state=MockState(location="tower"),
            memory=MockMemory(summary="Studied magic for years"),
        )

        renderer = PromptRenderer(config)
        result = renderer.render("nested_access", {"character": character})

        assert "Character: Боб" in result
        assert "Memory summary: Studied magic for years" in result
        assert "Triggers: Cast spells when threatened" in result


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_render_missing_variable(self, config_setup: tuple[Config, Path]) -> None:
        """Raises PromptRenderError on missing variable."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "missing_var.md"
        template.write_text("Hello, {{ name }}!\n", encoding="utf-8")

        renderer = PromptRenderer(config)

        with pytest.raises(PromptRenderError) as exc_info:
            renderer.render("missing_var", {})

        error_msg = str(exc_info.value)
        assert "missing_var" in error_msg.lower()
        assert "name" in error_msg

    def test_render_syntax_error(self, config_setup: tuple[Config, Path]) -> None:
        """Raises PromptRenderError on malformed Jinja2."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "syntax_error.md"
        template.write_text("Hello, {{ name }\n", encoding="utf-8")  # Missing closing brace

        renderer = PromptRenderer(config)

        with pytest.raises(PromptRenderError) as exc_info:
            renderer.render("syntax_error", {"name": "World"})

        error_msg = str(exc_info.value)
        assert "syntax" in error_msg.lower()
        assert "syntax_error" in error_msg

    def test_render_prompt_not_found(self, config_setup: tuple[Config, Path]) -> None:
        """Raises PromptNotFoundError when template doesn't exist."""
        config, _ = config_setup

        renderer = PromptRenderer(config)

        with pytest.raises(PromptNotFoundError) as exc_info:
            renderer.render("nonexistent_template", {})

        assert "not found" in str(exc_info.value).lower()


# =============================================================================
# Config Integration Tests
# =============================================================================


class TestConfigIntegration:
    """Tests for integration with Config."""

    def test_render_simulation_override(self, config_setup: tuple[Config, Path]) -> None:
        """Uses simulation prompt when it exists."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        # Create default template
        default_template = prompts_dir / "overridable.md"
        default_template.write_text("Default: {{ value }}\n", encoding="utf-8")

        # Create simulation override
        sim_path = tmp_path / "simulations" / "my-sim"
        sim_prompts = sim_path / "prompts"
        sim_prompts.mkdir(parents=True)
        override_template = sim_prompts / "overridable.md"
        override_template.write_text("Override: {{ value }}\n", encoding="utf-8")

        renderer = PromptRenderer(config, sim_path=sim_path)
        result = renderer.render("overridable", {"value": "тест"})

        assert result == "Override: тест\n"

    def test_render_fallback_to_default(self, config_setup: tuple[Config, Path]) -> None:
        """Uses default when simulation override is missing."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        # Create default template
        default_template = prompts_dir / "default_only.md"
        default_template.write_text("Default: {{ value }}\n", encoding="utf-8")

        # Create simulation folder without override
        sim_path = tmp_path / "simulations" / "my-sim"
        sim_path.mkdir(parents=True)

        renderer = PromptRenderer(config, sim_path=sim_path)
        result = renderer.render("default_only", {"value": "тест"})

        assert result == "Default: тест\n"


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_render_preserves_trailing_newline(self, config_setup: tuple[Config, Path]) -> None:
        """File ending newline is preserved."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        # Template with trailing newline
        template_with_newline = prompts_dir / "with_newline.md"
        template_with_newline.write_text("Content\n", encoding="utf-8")

        # Template without trailing newline
        template_no_newline = prompts_dir / "no_newline.md"
        template_no_newline.write_text("Content", encoding="utf-8")

        renderer = PromptRenderer(config)

        result_with = renderer.render("with_newline", {})
        assert result_with == "Content\n"

        result_without = renderer.render("no_newline", {})
        assert result_without == "Content"

    def test_render_unicode_content(self, config_setup: tuple[Config, Path]) -> None:
        """Non-ASCII characters are handled correctly."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "unicode.md"
        template.write_text(
            "Привет, {{ name }}! 日本語テスト 🎉\n",
            encoding="utf-8",
        )

        renderer = PromptRenderer(config)
        result = renderer.render("unicode", {"name": "Мир 世界"})

        assert "Привет, Мир 世界!" in result
        assert "日本語テスト" in result
        assert "🎉" in result

    def test_render_complex_template_with_pydantic(self, config_setup: tuple[Config, Path]) -> None:
        """Complex template with loops over Pydantic models."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "complex.md"
        template.write_text(
            """# {{ location.identity.name }}

{{ location.identity.description }}

**Right now:** {{ location.state.moment }}

**Connections:**
{% for conn in location.identity.connections -%}
- {{ conn.description }} → {{ conn.location_id }}
{% endfor %}
""",
            encoding="utf-8",
        )

        location = MockLocation(
            identity=MockLocationIdentity(
                id="tavern",
                name="Таверна",
                description="Уютное место для путников",
                connections=[
                    MockConnection(location_id="forest", description="Тропа на север"),
                    MockConnection(location_id="village", description="Дорога на юг"),
                ],
            ),
            state=MockLocationState(moment="Вечер, огонь потрескивает в камине"),
        )

        renderer = PromptRenderer(config)
        result = renderer.render("complex", {"location": location})

        assert "# Таверна" in result
        assert "Уютное место для путников" in result
        assert "Вечер, огонь потрескивает в камине" in result
        assert "Тропа на север → forest" in result
        assert "Дорога на юг → village" in result

    def test_render_memory_cells_loop(self, config_setup: tuple[Config, Path]) -> None:
        """Loop over memory cells works correctly."""
        config, tmp_path = config_setup
        prompts_dir = tmp_path / "src" / "prompts"

        template = prompts_dir / "memory.md"
        template.write_text(
            """## Memories

{% if character.memory.cells -%}
{% for cell in character.memory.cells -%}
- [Tick {{ cell.tick }}] {{ cell.text }}
{% endfor %}
{% else -%}
Nothing has happened yet.
{% endif %}
""",
            encoding="utf-8",
        )

        character = MockCharacter(
            identity=MockIdentity(id="bob", name="Bob", description="Test"),
            state=MockState(location="here"),
            memory=MockMemory(
                cells=[
                    MockMemoryCell(tick=1, text="Увидел дракона"),
                    MockMemoryCell(tick=2, text="Спрятался в пещере"),
                ],
                summary="",
            ),
        )

        renderer = PromptRenderer(config)
        result = renderer.render("memory", {"character": character})

        assert "[Tick 1] Увидел дракона" in result
        assert "[Tick 2] Спрятался в пещере" in result
