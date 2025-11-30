"""Unit tests for config module."""

import logging
from pathlib import Path

import pytest

from src.config import (
    Config,
    ConfigError,
    LLMConfig,
    PromptNotFoundError,
    SimulationConfig,
)


class TestSimulationConfig:
    """Tests for SimulationConfig model."""

    def test_default_memory_cells(self) -> None:
        config = SimulationConfig()
        assert config.memory_cells == 5

    def test_custom_memory_cells(self) -> None:
        config = SimulationConfig(memory_cells=7)
        assert config.memory_cells == 7

    def test_memory_cells_minimum_boundary(self) -> None:
        config = SimulationConfig(memory_cells=1)
        assert config.memory_cells == 1

    def test_memory_cells_maximum_boundary(self) -> None:
        config = SimulationConfig(memory_cells=10)
        assert config.memory_cells == 10


class TestLLMConfig:
    """Tests for LLMConfig placeholder model."""

    def test_llm_config_creates_successfully(self) -> None:
        config = LLMConfig()
        assert config is not None


class TestConfigLoad:
    """Tests for Config.load() method."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Successfully loads valid config.toml."""
        # Setup
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            "[simulation]\nmemory_cells = 7\n\n[llm]\n", encoding="utf-8"
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        # Execute
        config = Config.load(config_path=config_toml, project_root=tmp_path)

        # Verify
        assert config.simulation.memory_cells == 7
        assert config.llm is not None
        assert config.openai_api_key is None
        assert config.telegram_bot_token is None

    def test_load_missing_config(self, tmp_path: Path) -> None:
        """Raises ConfigError if config.toml is missing."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        missing_path = tmp_path / "config.toml"

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=missing_path, project_root=tmp_path)

        assert "not found" in str(exc_info.value).lower()

    def test_load_invalid_toml(self, tmp_path: Path) -> None:
        """Raises ConfigError for invalid TOML syntax."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            "[simulation\nmemory_cells = 5", encoding="utf-8"  # Missing closing bracket
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        assert "invalid toml" in str(exc_info.value).lower()

    def test_load_validation_error_memory_cells_zero(self, tmp_path: Path) -> None:
        """Raises ConfigError when memory_cells is 0 (below minimum)."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            "[simulation]\nmemory_cells = 0\n", encoding="utf-8"
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        error_msg = str(exc_info.value).lower()
        assert "memory_cells" in error_msg or "simulation" in error_msg

    def test_load_validation_error_memory_cells_too_high(self, tmp_path: Path) -> None:
        """Raises ConfigError when memory_cells exceeds maximum."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            "[simulation]\nmemory_cells = 15\n", encoding="utf-8"
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        error_msg = str(exc_info.value).lower()
        assert "memory_cells" in error_msg or "simulation" in error_msg

    def test_default_values_applied(self, tmp_path: Path) -> None:
        """Default values are applied when section/field is missing."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            "[llm]\n# Empty simulation section\n", encoding="utf-8"
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.simulation.memory_cells == 5  # Default value


class TestEnvLoading:
    """Tests for .env file loading."""

    def test_env_loading(self, tmp_path: Path) -> None:
        """Secrets are loaded from .env file."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text("[simulation]\nmemory_cells = 5\n", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENAI_API_KEY=sk-test-ключ-кириллица-123\n"
            "TELEGRAM_BOT_TOKEN=bot-токен-456\n",
            encoding="utf-8",
        )

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.openai_api_key == "sk-test-ключ-кириллица-123"
        assert config.telegram_bot_token == "bot-токен-456"

    def test_env_missing(self, tmp_path: Path) -> None:
        """Works without .env file, secrets are None."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text("[simulation]\nmemory_cells = 5\n", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")
        # No .env file created

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.openai_api_key is None
        assert config.telegram_bot_token is None


class TestResolvePrompt:
    """Tests for Config.resolve_prompt() method."""

    def test_resolve_prompt_default(self, tmp_path: Path) -> None:
        """Returns path to default prompt in src/prompts/."""
        # Setup project structure
        config_toml = tmp_path / "config.toml"
        config_toml.write_text("[simulation]\n", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)
        default_prompt = prompts_dir / "phase1_intention.md"
        default_prompt.write_text("# Default промпт\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)
        result = config.resolve_prompt("phase1_intention")

        assert result == default_prompt
        assert result.exists()

    def test_resolve_prompt_override(self, tmp_path: Path) -> None:
        """Returns path to simulation override when it exists."""
        # Setup project structure
        config_toml = tmp_path / "config.toml"
        config_toml.write_text("[simulation]\n", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)
        default_prompt = prompts_dir / "phase1_intention.md"
        default_prompt.write_text("# Default\n", encoding="utf-8")

        # Setup simulation override
        sim_path = tmp_path / "simulations" / "my-sim"
        sim_prompts = sim_path / "prompts"
        sim_prompts.mkdir(parents=True)
        override_prompt = sim_prompts / "phase1_intention.md"
        override_prompt.write_text("# Override промпт симуляции\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)
        result = config.resolve_prompt("phase1_intention", sim_path=sim_path)

        assert result == override_prompt
        assert result.exists()

    def test_resolve_prompt_missing_default(self, tmp_path: Path) -> None:
        """Raises PromptNotFoundError when default prompt is missing."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text("[simulation]\n", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)
        # No prompt file created

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        with pytest.raises(PromptNotFoundError) as exc_info:
            config.resolve_prompt("nonexistent_prompt")

        assert "not found" in str(exc_info.value).lower()

    def test_resolve_prompt_missing_override_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Logs warning and returns default when override is missing."""
        # Setup project structure
        config_toml = tmp_path / "config.toml"
        config_toml.write_text("[simulation]\n", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)
        default_prompt = prompts_dir / "phase2_master.md"
        default_prompt.write_text("# Default\n", encoding="utf-8")

        # Simulation path exists but has no prompts folder
        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        with caplog.at_level(logging.WARNING):
            result = config.resolve_prompt("phase2_master", sim_path=sim_path)

        # Should return default prompt
        assert result == default_prompt
        # Should log warning about missing override
        assert any("override not found" in record.message.lower() for record in caplog.records)

    def test_resolve_prompt_without_sim_path_returns_default(
        self, tmp_path: Path
    ) -> None:
        """Without sim_path, always returns default prompt."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text("[simulation]\n", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)
        default_prompt = prompts_dir / "phase4_summary.md"
        default_prompt.write_text("# Суммаризация памяти\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)
        result = config.resolve_prompt("phase4_summary")

        assert result == default_prompt


class TestProjectRootDetection:
    """Tests for project root auto-detection."""

    def test_find_project_root_raises_when_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises ConfigError when pyproject.toml not found."""
        # Create config but no pyproject.toml
        config_toml = tmp_path / "config.toml"
        config_toml.write_text("[simulation]\n", encoding="utf-8")

        # Mock _find_project_root to simulate not finding pyproject.toml
        def mock_find_project_root() -> Path:
            raise ConfigError("Could not find project root (no pyproject.toml found)")

        monkeypatch.setattr(Config, "_find_project_root", staticmethod(mock_find_project_root))

        # This should fail because project_root is not provided
        # and auto-detection will not find pyproject.toml
        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml)

        assert "project root" in str(exc_info.value).lower()
