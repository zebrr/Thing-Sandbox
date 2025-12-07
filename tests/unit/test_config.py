"""Unit tests for config module."""

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import (
    Config,
    ConfigError,
    ConsoleOutputConfig,
    FileOutputConfig,
    OutputConfig,
    PhaseConfig,
    PromptNotFoundError,
    SimulationConfig,
    TelegramOutputConfig,
)


# Helper to create minimal valid config with all phases
def make_minimal_config_toml(
    phase1_model: str = "test-model",
    phase2a_model: str = "test-model",
    phase2b_model: str = "test-model",
    phase4_model: str = "test-model",
    extra_phase1: str = "",
    extra_phase2a: str = "",
    extra_phase2b: str = "",
    extra_phase4: str = "",
    simulation: str = "",
) -> str:
    """Generate minimal valid config.toml content."""
    return f"""[simulation]
{simulation}

[phase1]
model = "{phase1_model}"
{extra_phase1}

[phase2a]
model = "{phase2a_model}"
{extra_phase2a}

[phase2b]
model = "{phase2b_model}"
{extra_phase2b}

[phase4]
model = "{phase4_model}"
{extra_phase4}
"""


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

    def test_default_mode_single(self) -> None:
        """Test default_mode='single' loads correctly."""
        config = SimulationConfig(default_mode="single")
        assert config.default_mode == "single"

    def test_default_mode_continuous(self) -> None:
        """Test default_mode='continuous' loads correctly."""
        config = SimulationConfig(default_mode="continuous")
        assert config.default_mode == "continuous"

    def test_default_mode_default_value(self) -> None:
        """Test default_mode defaults to 'single'."""
        config = SimulationConfig()
        assert config.default_mode == "single"

    def test_default_interval_valid(self) -> None:
        """Test default_interval >= 1 loads correctly."""
        config = SimulationConfig(default_interval=300)
        assert config.default_interval == 300

    def test_default_interval_minimum_boundary(self) -> None:
        """Test default_interval = 1 is valid."""
        config = SimulationConfig(default_interval=1)
        assert config.default_interval == 1

    def test_default_interval_default_value(self) -> None:
        """Test default_interval defaults to 600."""
        config = SimulationConfig()
        assert config.default_interval == 600

    def test_default_ticks_limit_zero(self) -> None:
        """Test default_ticks_limit = 0 means unlimited."""
        config = SimulationConfig(default_ticks_limit=0)
        assert config.default_ticks_limit == 0

    def test_default_ticks_limit_positive(self) -> None:
        """Test positive default_ticks_limit loads correctly."""
        config = SimulationConfig(default_ticks_limit=10)
        assert config.default_ticks_limit == 10

    def test_default_ticks_limit_default_value(self) -> None:
        """Test default_ticks_limit defaults to 0."""
        config = SimulationConfig()
        assert config.default_ticks_limit == 0

    def test_default_mode_invalid(self) -> None:
        """Test invalid default_mode raises ValidationError."""
        with pytest.raises(ValidationError):
            SimulationConfig(default_mode="invalid")  # type: ignore[arg-type]

    def test_default_interval_invalid(self) -> None:
        """Test default_interval < 1 raises ValidationError."""
        with pytest.raises(ValidationError):
            SimulationConfig(default_interval=0)

    def test_default_ticks_limit_negative_invalid(self) -> None:
        """Test default_ticks_limit < 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            SimulationConfig(default_ticks_limit=-1)


class TestPhaseConfig:
    """Tests for PhaseConfig model."""

    def test_phase_config_with_required_model(self) -> None:
        config = PhaseConfig(model="gpt-4o")
        assert config.model == "gpt-4o"
        assert config.timeout == 600  # Default

    def test_phase_config_all_defaults(self) -> None:
        config = PhaseConfig(model="test-model")
        assert config.is_reasoning is False
        assert config.max_context_tokens == 128000
        assert config.max_completion == 4096
        assert config.timeout == 600
        assert config.max_retries == 3
        assert config.reasoning_effort is None
        assert config.reasoning_summary is None
        assert config.verbosity is None
        assert config.truncation is None
        assert config.response_chain_depth == 0

    def test_phase_config_custom_values(self) -> None:
        config = PhaseConfig(
            model="gpt-5-mini",
            is_reasoning=True,
            max_context_tokens=400000,
            max_completion=128000,
            timeout=300,
            max_retries=5,
            reasoning_effort="high",
            reasoning_summary="detailed",
            verbosity="low",
            truncation="disabled",
            response_chain_depth=2,
        )
        assert config.model == "gpt-5-mini"
        assert config.is_reasoning is True
        assert config.max_context_tokens == 400000
        assert config.max_completion == 128000
        assert config.timeout == 300
        assert config.max_retries == 5
        assert config.reasoning_effort == "high"
        assert config.reasoning_summary == "detailed"
        assert config.verbosity == "low"
        assert config.truncation == "disabled"
        assert config.response_chain_depth == 2


class TestConfigLoad:
    """Tests for Config.load() method."""

    def test_load_valid_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successfully loads valid config.toml with all phases."""
        # Isolate from real environment
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(
                simulation="memory_cells = 7",
                phase1_model="model-phase1",
                phase2a_model="model-phase2a",
            ),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.simulation.memory_cells == 7
        assert config.phase1.model == "model-phase1"
        assert config.phase2a.model == "model-phase2a"
        assert config.phase2b.model == "test-model"
        assert config.phase4.model == "test-model"
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
            "[simulation\nmemory_cells = 5",
            encoding="utf-8",  # Missing closing bracket
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
            make_minimal_config_toml(simulation="memory_cells = 0"),
            encoding="utf-8",
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
            make_minimal_config_toml(simulation="memory_cells = 15"),
            encoding="utf-8",
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
            make_minimal_config_toml(),  # No explicit memory_cells
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.simulation.memory_cells == 5  # Default value

    def test_load_default_mode_invalid(self, tmp_path: Path) -> None:
        """Raises ConfigError when default_mode is invalid."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(simulation='default_mode = "invalid"'),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        error_msg = str(exc_info.value).lower()
        assert "default_mode" in error_msg or "simulation" in error_msg

    def test_load_default_interval_invalid(self, tmp_path: Path) -> None:
        """Raises ConfigError when default_interval < 1."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(simulation="default_interval = 0"),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        error_msg = str(exc_info.value).lower()
        assert "default_interval" in error_msg or "simulation" in error_msg

    def test_load_new_simulation_fields(self, tmp_path: Path) -> None:
        """New simulation fields are loaded correctly from config.toml."""
        config_toml = tmp_path / "config.toml"
        simulation_config = (
            'default_mode = "continuous"\ndefault_interval = 300\ndefault_ticks_limit = 10'
        )
        config_toml.write_text(
            make_minimal_config_toml(simulation=simulation_config),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.simulation.default_mode == "continuous"
        assert config.simulation.default_interval == 300
        assert config.simulation.default_ticks_limit == 10


class TestPhaseConfigLoading:
    """Tests for PhaseConfig loading from config.toml."""

    def test_phase_config_loading(self, tmp_path: Path) -> None:
        """All phase configs loaded correctly."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            """[simulation]
memory_cells = 5

[phase1]
model = "gpt-5-mini-2025-08-07"
is_reasoning = true
timeout = 600
response_chain_depth = 0

[phase2a]
model = "gpt-5.1-2025-11-13"
is_reasoning = true
response_chain_depth = 2

[phase2b]
model = "gpt-5-mini-2025-08-07"
timeout = 600

[phase4]
model = "gpt-5-mini-2025-08-07"
is_reasoning = true
""",
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.phase1.model == "gpt-5-mini-2025-08-07"
        assert config.phase2a.response_chain_depth == 2
        assert config.phase2b.timeout == 600
        assert config.phase4.is_reasoning is True

    def test_phase_config_defaults(self, tmp_path: Path) -> None:
        """Default values applied when not specified in TOML."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        # Verify defaults are applied
        assert config.phase1.is_reasoning is False
        assert config.phase1.max_context_tokens == 128000
        assert config.phase1.max_completion == 4096
        assert config.phase1.timeout == 600
        assert config.phase1.max_retries == 3
        assert config.phase1.response_chain_depth == 0

    def test_phase_config_model_required(self, tmp_path: Path) -> None:
        """Missing model field raises ConfigError."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            """[simulation]

[phase1]
# model is missing!
is_reasoning = true

[phase2a]
model = "test-model"

[phase2b]
model = "test-model"

[phase4]
model = "test-model"
""",
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        error_msg = str(exc_info.value)
        assert "phase1" in error_msg
        assert "model" in error_msg

    def test_phase_config_invalid_reasoning_effort(self, tmp_path: Path) -> None:
        """Invalid reasoning_effort value raises ConfigError."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(extra_phase1='reasoning_effort = "extreme"'),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        error_msg = str(exc_info.value)
        assert "phase1" in error_msg
        assert "reasoning_effort" in error_msg

    def test_phase_config_invalid_timeout(self, tmp_path: Path) -> None:
        """Timeout < 1 raises ConfigError."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(extra_phase2a="timeout = 0"),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        error_msg = str(exc_info.value)
        assert "phase2a" in error_msg
        assert "timeout" in error_msg

    def test_phase_config_optional_none(self, tmp_path: Path) -> None:
        """Omitted optional fields result in None."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.phase1.verbosity is None
        assert config.phase1.reasoning_effort is None
        assert config.phase1.reasoning_summary is None
        assert config.phase1.truncation is None

    def test_phase_config_missing_section(self, tmp_path: Path) -> None:
        """Missing phase section raises ConfigError."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            """[simulation]

[phase1]
model = "test-model"

[phase2b]
model = "test-model"

[phase4]
model = "test-model"
""",  # Missing [phase2a]
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml, project_root=tmp_path)

        error_msg = str(exc_info.value)
        assert "phase2a" in error_msg
        assert "missing" in error_msg.lower()

    def test_phase_config_all_phases_present(self, tmp_path: Path) -> None:
        """All phase configs (phase1, phase2a, phase2b, phase4) are accessible."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(
                phase1_model="model-1",
                phase2a_model="model-2a",
                phase2b_model="model-2b",
                phase4_model="model-4",
            ),
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.phase1.model == "model-1"
        assert config.phase2a.model == "model-2a"
        assert config.phase2b.model == "model-2b"
        assert config.phase4.model == "model-4"


class TestEnvLoading:
    """Tests for .env file loading."""

    def test_env_loading(self, tmp_path: Path) -> None:
        """Secrets are loaded from .env file."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENAI_API_KEY=sk-test-ключ-кириллица-123\nTELEGRAM_BOT_TOKEN=bot-токен-456\n",
            encoding="utf-8",
        )

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.openai_api_key == "sk-test-ключ-кириллица-123"
        assert config.telegram_bot_token == "bot-токен-456"

    def test_env_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Works without .env file, secrets are None."""
        # Clean up env vars that might be set by previous tests
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        config_toml = tmp_path / "config.toml"
        config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")
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
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")
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
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)
        default_prompt = prompts_dir / "phase1_intention.md"
        default_prompt.write_text("# Default\n", encoding="utf-8")

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
        config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        with pytest.raises(PromptNotFoundError) as exc_info:
            config.resolve_prompt("nonexistent_prompt")

        assert "not found" in str(exc_info.value).lower()

    def test_resolve_prompt_missing_override_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Logs warning and returns default when override is missing."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)
        default_prompt = prompts_dir / "phase2_master.md"
        default_prompt.write_text("# Default\n", encoding="utf-8")

        sim_path = tmp_path / "simulations" / "test-sim"
        sim_path.mkdir(parents=True)

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        with caplog.at_level(logging.WARNING):
            result = config.resolve_prompt("phase2_master", sim_path=sim_path)

        assert result == default_prompt
        assert any("override not found" in record.message.lower() for record in caplog.records)

    def test_resolve_prompt_without_sim_path_returns_default(self, tmp_path: Path) -> None:
        """Without sim_path, always returns default prompt."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")
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
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(make_minimal_config_toml(), encoding="utf-8")

        def mock_find_project_root() -> Path:
            raise ConfigError("Could not find project root (no pyproject.toml found)")

        monkeypatch.setattr(Config, "_find_project_root", staticmethod(mock_find_project_root))

        with pytest.raises(ConfigError) as exc_info:
            Config.load(config_path=config_toml)

        assert "project root" in str(exc_info.value).lower()


class TestOutputConfig:
    """Tests for OutputConfig and related models."""

    def test_output_config_defaults(self) -> None:
        """OutputConfig has sensible defaults."""
        config = OutputConfig()
        assert config.console.enabled is True
        assert config.console.show_narratives is True
        assert config.file.enabled is True
        assert config.telegram.enabled is False
        assert config.telegram.chat_id == ""

    def test_console_output_config_custom(self) -> None:
        """ConsoleOutputConfig accepts custom values."""
        config = ConsoleOutputConfig(enabled=False, show_narratives=False)
        assert config.enabled is False
        assert config.show_narratives is False

    def test_file_output_config_custom(self) -> None:
        """FileOutputConfig accepts custom values."""
        config = FileOutputConfig(enabled=False)
        assert config.enabled is False

    def test_telegram_output_config_custom(self) -> None:
        """TelegramOutputConfig accepts custom values."""
        config = TelegramOutputConfig(enabled=True, chat_id="123456789")
        assert config.enabled is True
        assert config.chat_id == "123456789"

    def test_output_config_from_toml(self, tmp_path: Path) -> None:
        """Output config is loaded correctly from config.toml."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml()
            + """
[output.console]
enabled = false
show_narratives = false

[output.file]
enabled = true

[output.telegram]
enabled = true
chat_id = "test-chat-кириллица-123"
""",
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.output.console.enabled is False
        assert config.output.console.show_narratives is False
        assert config.output.file.enabled is True
        assert config.output.telegram.enabled is True
        assert config.output.telegram.chat_id == "test-chat-кириллица-123"

    def test_output_config_missing_uses_defaults(self, tmp_path: Path) -> None:
        """Missing output section uses defaults."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml(),  # No [output] section
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        assert config.output.console.enabled is True
        assert config.output.console.show_narratives is True
        assert config.output.file.enabled is True
        assert config.output.telegram.enabled is False
        assert config.output.telegram.chat_id == ""

    def test_output_config_partial_section(self, tmp_path: Path) -> None:
        """Partial output section fills missing with defaults."""
        config_toml = tmp_path / "config.toml"
        config_toml.write_text(
            make_minimal_config_toml()
            + """
[output.telegram]
enabled = true
chat_id = "42"
""",
            encoding="utf-8",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n", encoding="utf-8")

        config = Config.load(config_path=config_toml, project_root=tmp_path)

        # console and file should have defaults
        assert config.output.console.enabled is True
        assert config.output.file.enabled is True
        # telegram should have custom values
        assert config.output.telegram.enabled is True
        assert config.output.telegram.chat_id == "42"
