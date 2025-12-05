"""Prompt rendering module for Thing' Sandbox.

Loads Jinja2 templates and renders them with simulation context.
Integrates with Config for template resolution.

Example:
    >>> from pathlib import Path
    >>> from src.config import Config
    >>> from src.utils.prompts import PromptRenderer
    >>> config = Config.load()
    >>> renderer = PromptRenderer(config, sim_path=Path("simulations/demo-sim"))
    >>> result = renderer.render("phase1_intention_system", {})
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

from src.config import Config, PromptNotFoundError

logger = logging.getLogger(__name__)


class PromptRenderError(Exception):
    """Raised when prompt rendering fails.

    This includes missing variables in context, Jinja2 syntax errors,
    and file read errors.
    """

    pass


class PromptRenderer:
    """Loads and renders Jinja2 prompt templates.

    Uses Config.resolve_prompt() for template path resolution with
    simulation override support.

    Example:
        >>> config = Config.load()
        >>> renderer = PromptRenderer(config)
        >>> result = renderer.render("phase1_intention_system", {})
    """

    def __init__(self, config: Config, sim_path: Path | None = None) -> None:
        """Initialize renderer with configuration and optional simulation path.

        Args:
            config: Application configuration instance.
            sim_path: Path to simulation folder for override resolution.
        """
        self._config = config
        self._sim_path = sim_path
        self._env = Environment(
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render prompt template with given context.

        Args:
            template_name: Template identifier without extension
                (e.g., "phase1_intention_system").
            context: Variables for Jinja2 substitution.

        Returns:
            Rendered prompt text.

        Raises:
            PromptNotFoundError: Template file not found.
            PromptRenderError: Rendering failed (missing variable,
                syntax error, IO error).
        """
        # Resolve template path (may raise PromptNotFoundError)
        template_path = self._config.resolve_prompt(template_name, self._sim_path)
        logger.debug("Template path resolved: %s", template_path)

        # Read template file
        try:
            template_source = template_path.read_text(encoding="utf-8")
        except OSError as e:
            raise PromptRenderError(f"Cannot read '{template_name}': {e}") from e

        # Compile template
        try:
            template = self._env.from_string(template_source)
        except TemplateSyntaxError as e:
            raise PromptRenderError(f"Syntax error in '{template_name}': {e.message}") from e

        # Render template
        try:
            return template.render(context)
        except UndefinedError as e:
            raise PromptRenderError(f"Missing variable in '{template_name}': {e}") from e


# Re-export for convenience
__all__ = ["PromptRenderer", "PromptRenderError", "PromptNotFoundError"]
