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

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

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


class LLMConfig(BaseModel):
    """LLM client configuration settings.

    Placeholder for A.5 implementation.

    Example:
        >>> config = LLMConfig()
    """

    pass


class EnvSettings(BaseSettings):
    """Environment variables loader using pydantic-settings.

    Loads secrets from .env file if present.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = None
    telegram_bot_token: str | None = None


def _load_env_settings(env_file_path: Path | None) -> EnvSettings:
    """Load environment settings from specified .env file.

    Args:
        env_file_path: Path to .env file, or None to skip file loading.

    Returns:
        EnvSettings instance with loaded values.
    """
    if env_file_path is not None and env_file_path.exists():
        # Read .env file manually and pass values
        env_vars: dict[str, str | None] = {}
        with open(env_file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip().lower()
                    value = value.strip()
                    if value:
                        env_vars[key] = value

        return EnvSettings(
            openai_api_key=env_vars.get("openai_api_key"),
            telegram_bot_token=env_vars.get("telegram_bot_token"),
        )

    return EnvSettings(
        openai_api_key=None,
        telegram_bot_token=None,
        _env_file=None,  # type: ignore[call-arg]
    )


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
        llm: LLMConfig,
        openai_api_key: str | None,
        telegram_bot_token: str | None,
        project_root: Path,
    ) -> None:
        """Initialize Config instance.

        Args:
            simulation: Simulation configuration settings.
            llm: LLM configuration settings.
            openai_api_key: OpenAI API key from .env.
            telegram_bot_token: Telegram bot token from .env.
            project_root: Project root directory path.
        """
        self.simulation = simulation
        self.llm = llm
        self.openai_api_key = openai_api_key
        self.telegram_bot_token = telegram_bot_token
        self._project_root = project_root

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

        # Parse LLM config (placeholder)
        llm_data = toml_data.get("llm", {})
        try:
            llm = LLMConfig(**llm_data)
        except ValidationError as e:
            raise ConfigError(f"Validation error in llm config: {e}")

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
            llm=llm,
            openai_api_key=env_settings.openai_api_key,
            telegram_bot_token=env_settings.telegram_bot_token,
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
        default_path = self._project_root / "src" / "prompts" / prompt_filename
        if default_path.exists():
            logger.debug("Using default prompt: %s", default_path)
            return default_path

        raise PromptNotFoundError(f"Default prompt not found: {default_path}")
