"""Configuration loader for Thing' Sandbox.

Loads application settings from config.toml and secrets from .env,
provides prompt resolution with simulation-specific overrides.

Example:
    >>> from src.config import Config
    >>> config = Config.load()
    >>> print(config.simulation.memory_cells)  # 5
    >>> print(config.openai_api_key)  # sk-...
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.utils.storage import Simulation

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration loading fails.

    This includes missing config.toml, invalid TOML syntax,
    and validation errors for configuration values.
    """

    pass


class PromptNotFoundError(Exception):
    """Raised when required prompt file not found.

    This occurs when the default prompt file does not exist
    in src/prompts/ directory.
    """

    pass


class SimulationConfig(BaseModel):
    """Simulation-related configuration settings.

    Example:
        >>> config = SimulationConfig(memory_cells=7)
        >>> config.memory_cells
        7
    """

    memory_cells: int = Field(ge=1, le=10, default=5)
    default_mode: Literal["single", "continuous"] = "single"
    default_interval: int = Field(ge=1, default=600)  # seconds
    default_ticks_limit: int = Field(ge=0, default=0)  # 0 = unlimited


class PhaseConfig(BaseModel):
    """Configuration for a single LLM phase.

    All phases share the same structure but may have different values.
    Fields with None value are not passed to OpenAI API.

    Example:
        >>> config = PhaseConfig(model="gpt-4o")
        >>> config.timeout
        600
    """

    model: str
    is_reasoning: bool = False
    max_context_tokens: int = Field(ge=1, default=128000)
    max_completion: int = Field(ge=1, default=4096)
    timeout: int = Field(ge=1, default=600)
    max_retries: int = Field(ge=0, le=10, default=3)
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    reasoning_summary: Literal["auto", "concise", "detailed"] | None = None
    verbosity: Literal["low", "medium", "high"] | None = None
    truncation: Literal["auto", "disabled"] | None = None
    response_chain_depth: int = Field(ge=0, default=0)


class ConsoleOutputConfig(BaseModel):
    """Console output configuration.

    Example:
        >>> config = ConsoleOutputConfig(show_narratives=False)
        >>> config.show_narratives
        False
    """

    show_narratives: bool = True


class FileOutputConfig(BaseModel):
    """File output configuration (TickLogger).

    Example:
        >>> config = FileOutputConfig(enabled=False)
        >>> config.enabled
        False
    """

    enabled: bool = True


class TelegramOutputConfig(BaseModel):
    """Telegram output configuration.

    Example:
        >>> config = TelegramOutputConfig(enabled=True, chat_id="123456", mode="full")
        >>> config.chat_id
        '123456'
        >>> config.mode
        'full'
    """

    enabled: bool = False
    chat_id: str = ""
    mode: Literal["none", "narratives", "narratives_stats", "full", "full_stats"] = "none"
    group_intentions: bool = True
    group_narratives: bool = True
    message_thread_id: int | None = None


class OutputConfig(BaseModel):
    """Output configuration section.

    Controls output channels: console, file (TickLogger), and telegram.

    Example:
        >>> config = OutputConfig()
        >>> config.console.enabled
        True
        >>> config.telegram.enabled
        False
    """

    console: ConsoleOutputConfig = Field(default_factory=ConsoleOutputConfig)
    file: FileOutputConfig = Field(default_factory=FileOutputConfig)
    telegram: TelegramOutputConfig = Field(default_factory=TelegramOutputConfig)


class EnvSettings(BaseSettings):
    """Environment variables loader using pydantic-settings.

    Reads from os.environ after load_dotenv() populates it.
    """

    openai_api_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_test_chat_id: str | None = None
    telegram_test_thread_id: int | None = None


def _load_env_settings(env_file_path: Path | None) -> EnvSettings:
    """Load environment settings from specified .env file.

    Uses python-dotenv to load .env into os.environ,
    then pydantic-settings reads from there.

    Args:
        env_file_path: Path to .env file, or None to skip file loading.

    Returns:
        EnvSettings instance with loaded values.
    """
    if env_file_path is not None and env_file_path.exists():
        load_dotenv(env_file_path, override=True)

    return EnvSettings()


class Config:
    """Main configuration class for Thing' Sandbox.

    Loads configuration from config.toml and secrets from .env.
    Provides prompt resolution with simulation-specific overrides.

    Example:
        >>> config = Config.load()
        >>> print(config.simulation.memory_cells)
        5
        >>> prompt_path = config.resolve_prompt("phase1_intention")
    """

    def __init__(
        self,
        simulation: SimulationConfig,
        phase1: PhaseConfig,
        phase2a: PhaseConfig,
        phase2b: PhaseConfig,
        phase4: PhaseConfig,
        output: OutputConfig,
        openai_api_key: str | None,
        telegram_bot_token: str | None,
        telegram_test_chat_id: str | None,
        telegram_test_thread_id: int | None,
        project_root: Path,
    ) -> None:
        """Initialize Config instance.

        Args:
            simulation: Simulation configuration settings.
            phase1: LLM configuration for Phase 1 (character intentions).
            phase2a: LLM configuration for Phase 2a (game master arbitration).
            phase2b: LLM configuration for Phase 2b (narrative generation).
            phase4: LLM configuration for Phase 4 (memory summarization).
            output: Output configuration for console, file, and telegram.
            openai_api_key: OpenAI API key from .env.
            telegram_bot_token: Telegram bot token from .env.
            telegram_test_chat_id: Default chat ID from .env (fallback).
            telegram_test_thread_id: Default thread ID from .env (fallback).
            project_root: Project root directory path.
        """
        self.simulation = simulation
        self.phase1 = phase1
        self.phase2a = phase2a
        self.phase2b = phase2b
        self.phase4 = phase4
        self.output = output
        self.openai_api_key = openai_api_key
        self.telegram_bot_token = telegram_bot_token
        self.telegram_test_chat_id = telegram_test_chat_id
        self.telegram_test_thread_id = telegram_test_thread_id
        self.project_root = project_root

    @classmethod
    def load(
        cls,
        config_path: Path | None = None,
        project_root: Path | None = None,
    ) -> Config:
        """Load configuration from files.

        Args:
            config_path: Path to config.toml. If None, uses project root.
            project_root: Project root directory. If None, auto-detects
                by walking up from this file looking for pyproject.toml.

        Returns:
            Config instance with all settings loaded.

        Raises:
            ConfigError: If config.toml is missing, has invalid syntax,
                or contains invalid values.
        """
        # Determine project root
        if project_root is None:
            project_root = cls._find_project_root()

        # Determine config.toml path
        if config_path is None:
            config_path = project_root / "config.toml"

        # Load config.toml
        if not config_path.exists():
            raise ConfigError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, "rb") as f:
                toml_data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Invalid TOML syntax in {config_path}: {e}")

        # Parse simulation config
        simulation_data = toml_data.get("simulation", {})
        try:
            simulation = SimulationConfig(**simulation_data)
        except ValidationError as e:
            errors = e.errors()
            if errors:
                err = errors[0]
                field = ".".join(str(loc) for loc in err["loc"])
                msg = err["msg"]
                value = simulation_data.get(err["loc"][0]) if err["loc"] else None
                raise ConfigError(f"Config error: simulation.{field} {msg}, got {value}")
            raise ConfigError(f"Validation error in simulation config: {e}")

        # Parse phase configs
        phase_names = ["phase1", "phase2a", "phase2b", "phase4"]
        phase_configs: dict[str, PhaseConfig] = {}

        for phase_name in phase_names:
            if phase_name not in toml_data:
                raise ConfigError(f"Config error: missing [{phase_name}] section")

            phase_data = toml_data[phase_name]
            try:
                phase_configs[phase_name] = PhaseConfig(**phase_data)
            except ValidationError as e:
                errors = e.errors()
                if errors:
                    err = errors[0]
                    field = str(err["loc"][0]) if err["loc"] else "unknown"
                    msg = err["msg"]
                    raise ConfigError(
                        f"Config error: {phase_name} validation failed: {msg} [{field}]"
                    )
                raise ConfigError(f"Validation error in {phase_name} config: {e}")

        # Parse output config (optional section, defaults if missing)
        output_data = toml_data.get("output", {})
        try:
            output = OutputConfig(
                console=ConsoleOutputConfig(**output_data.get("console", {})),
                file=FileOutputConfig(**output_data.get("file", {})),
                telegram=TelegramOutputConfig(**output_data.get("telegram", {})),
            )
        except ValidationError as e:
            errors = e.errors()
            if errors:
                err = errors[0]
                field = ".".join(str(loc) for loc in err["loc"])
                msg = err["msg"]
                raise ConfigError(f"Config error: output.{field} {msg}")
            raise ConfigError(f"Validation error in output config: {e}")

        # Load environment variables
        env_file = project_root / ".env"
        env_settings = _load_env_settings(env_file if env_file.exists() else None)

        logger.debug(
            "Config loaded: memory_cells=%d, api_key=%s",
            simulation.memory_cells,
            "***" if env_settings.openai_api_key else "None",
        )

        return cls(
            simulation=simulation,
            phase1=phase_configs["phase1"],
            phase2a=phase_configs["phase2a"],
            phase2b=phase_configs["phase2b"],
            phase4=phase_configs["phase4"],
            output=output,
            openai_api_key=env_settings.openai_api_key,
            telegram_bot_token=env_settings.telegram_bot_token,
            telegram_test_chat_id=env_settings.telegram_test_chat_id,
            telegram_test_thread_id=env_settings.telegram_test_thread_id,
            project_root=project_root,
        )

    @staticmethod
    def _find_project_root() -> Path:
        """Find project root by walking up from this file.

        Looks for pyproject.toml to identify project root.

        Returns:
            Path to project root directory.

        Raises:
            ConfigError: If pyproject.toml not found in any parent.
        """
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent

        raise ConfigError("Could not find project root (no pyproject.toml found)")

    def resolve_prompt(
        self,
        prompt_name: str,
        sim_path: Path | None = None,
    ) -> Path:
        """Resolve prompt file path with simulation override support.

        Resolution order:
        1. {sim_path}/prompts/{prompt_name}.md (if sim_path provided and exists)
        2. src/prompts/{prompt_name}.md (default)

        Args:
            prompt_name: Prompt identifier without extension (e.g., "phase1_intention").
            sim_path: Path to simulation folder (optional).

        Returns:
            Path to prompt file.

        Raises:
            PromptNotFoundError: If default prompt file not found.
        """
        prompt_filename = f"{prompt_name}.md"

        # Check simulation override
        if sim_path is not None:
            override_path = sim_path / "prompts" / prompt_filename
            if override_path.exists():
                logger.debug("Using simulation prompt override: %s", override_path)
                return override_path
            else:
                logger.warning(
                    "Simulation prompt override not found: %s, using default",
                    override_path,
                )

        # Check default prompt
        default_path = self.project_root / "src" / "prompts" / prompt_filename
        if default_path.exists():
            logger.debug("Using default prompt: %s", default_path)
            return default_path

        raise PromptNotFoundError(f"Default prompt not found: {default_path}")

    def resolve_output(self, simulation: Simulation | None = None) -> OutputConfig:
        """Merge config.toml defaults with simulation.json overrides.

        Args:
            simulation: Loaded simulation with potential output overrides in __pydantic_extra__.
                       If None, returns defaults from config.toml.

        Returns:
            OutputConfig with merged values.

        Example:
            >>> config = Config.load()
            >>> simulation = load_simulation(sim_path)
            >>> output_config = config.resolve_output(simulation)
            >>> print(output_config.telegram.enabled)
        """
        # Start with defaults as dicts
        console_data = self.output.console.model_dump()
        file_data = self.output.file.model_dump()
        telegram_data = self.output.telegram.model_dump()

        # Merge overrides from simulation if present
        if simulation is not None:
            extra = simulation.__pydantic_extra__ or {}
            override = extra.get("output", {})

            if "console" in override:
                console_data.update(override["console"])
            if "file" in override:
                file_data.update(override["file"])
            if "telegram" in override:
                telegram_data.update(override["telegram"])

        # Fallback: if chat_id empty after merge, use TELEGRAM_TEST_CHAT_ID from .env
        if not telegram_data.get("chat_id") and self.telegram_test_chat_id:
            telegram_data["chat_id"] = self.telegram_test_chat_id

        # Normalize empty string to None for message_thread_id
        if telegram_data.get("message_thread_id") == "":
            telegram_data["message_thread_id"] = None

        # Fallback: if message_thread_id is None after merge, use TELEGRAM_TEST_THREAD_ID from .env
        if telegram_data.get("message_thread_id") is None and self.telegram_test_thread_id:
            telegram_data["message_thread_id"] = self.telegram_test_thread_id

        return OutputConfig(
            console=ConsoleOutputConfig.model_validate(console_data),
            file=FileOutputConfig.model_validate(file_data),
            telegram=TelegramOutputConfig.model_validate(telegram_data),
        )
