"""Command-line interface for Thing' Sandbox.

Entry point for running simulations and checking their status.

Example:
    >>> # Run a single tick
    >>> python -m src.cli run demo-sim
    >>> # Check simulation status
    >>> python -m src.cli status demo-sim
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from src.config import Config, ConfigError, OutputConfig
from src.narrators import ConsoleNarrator, Narrator, TelegramNarrator
from src.runner import PhaseError, SimulationBusyError, TickRunner
from src.utils.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_IO_ERROR,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
)
from src.utils.logging_config import setup_logging
from src.utils.storage import (
    InvalidDataError,
    Simulation,
    SimulationNotFoundError,
    StorageIOError,
    TemplateNotFoundError,
    load_simulation,
    reset_simulation,
)
from src.utils.telegram_client import TelegramClient

app = typer.Typer(
    name="thing-sandbox",
    help="Thing' Sandbox - LLM-driven text simulation",
)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Thing' Sandbox CLI - LLM-driven text simulation."""
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(level=level)


@app.command()
def run(sim_id: str) -> None:
    """Run simulation tick.

    Executes one complete tick of the specified simulation,
    running all phases and outputting narratives to console.

    Args:
        sim_id: Simulation identifier (folder name in simulations/).
    """
    try:
        config = Config.load()
    except ConfigError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    sim_path = config.project_root / "simulations" / sim_id

    # Load simulation BEFORE creating narrators
    try:
        simulation = load_simulation(sim_path)
    except SimulationNotFoundError:
        typer.echo(f"Simulation '{sim_id}' not found", err=True)
        raise typer.Exit(code=EXIT_INPUT_ERROR)
    except InvalidDataError as e:
        typer.echo(f"Invalid simulation data: {e}", err=True)
        raise typer.Exit(code=EXIT_INPUT_ERROR)

    # Resolve output config with simulation overrides
    output_config = config.resolve_output(simulation)

    try:
        asyncio.run(_run_tick(config, simulation, sim_path, output_config))
    except SimulationBusyError:
        typer.echo(f"Simulation '{sim_id}' is busy", err=True)
        raise typer.Exit(code=EXIT_RUNTIME_ERROR)
    except PhaseError as e:
        typer.echo(f"Phase failed: {e}", err=True)
        raise typer.Exit(code=EXIT_RUNTIME_ERROR)
    except StorageIOError as e:
        typer.echo(f"Storage error: {e}", err=True)
        raise typer.Exit(code=EXIT_IO_ERROR)


async def _run_tick(
    config: Config,
    simulation: Simulation,
    sim_path: Path,
    output_config: OutputConfig,
) -> None:
    """Execute tick asynchronously.

    Args:
        config: Application configuration.
        simulation: Loaded simulation instance.
        sim_path: Path to simulation folder.
        output_config: Resolved output configuration.
    """
    narrators: list[Narrator] = [
        ConsoleNarrator(show_narratives=output_config.console.show_narratives)
    ]

    # Telegram narrator (if enabled and mode != none)
    if output_config.telegram.enabled and output_config.telegram.mode != "none":
        if not config.telegram_bot_token:
            typer.echo("Telegram enabled but TELEGRAM_BOT_TOKEN not set", err=True)
        else:
            client = TelegramClient(config.telegram_bot_token)
            narrators.append(
                TelegramNarrator(
                    client=client,
                    chat_id=output_config.telegram.chat_id,
                    mode=output_config.telegram.mode,
                    group_intentions=output_config.telegram.group_intentions,
                    group_narratives=output_config.telegram.group_narratives,
                )
            )

    runner = TickRunner(config, narrators)

    await runner.run_tick(simulation, sim_path)


@app.command()
def status(sim_id: str) -> None:
    """Show simulation status.

    Displays current tick, character count, location count, and status.

    Args:
        sim_id: Simulation identifier (folder name in simulations/).
    """
    try:
        config = Config.load()
    except ConfigError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    sim_path = config.project_root / "simulations" / sim_id

    try:
        simulation = load_simulation(sim_path)
    except SimulationNotFoundError:
        typer.echo(f"Simulation '{sim_id}' not found", err=True)
        raise typer.Exit(code=EXIT_INPUT_ERROR)
    except InvalidDataError as e:
        typer.echo(f"Invalid simulation data: {e}", err=True)
        raise typer.Exit(code=EXIT_INPUT_ERROR)

    char_count = len(simulation.characters)
    loc_count = len(simulation.locations)

    typer.echo(
        f"{sim_id}: tick {simulation.current_tick}, "
        f"{char_count} characters, {loc_count} locations, "
        f"status: {simulation.status}"
    )

    raise typer.Exit(code=EXIT_SUCCESS)


@app.command()
def reset(sim_id: str) -> None:
    """Reset simulation to template state.

    Copies template over working simulation, clearing logs.
    Creates simulation folder if it doesn't exist.

    Args:
        sim_id: Simulation identifier (folder name in simulations/).
    """
    try:
        config = Config.load()
    except ConfigError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    try:
        reset_simulation(sim_id, config.project_root)
    except TemplateNotFoundError:
        typer.echo(f"Template for '{sim_id}' not found", err=True)
        raise typer.Exit(code=EXIT_INPUT_ERROR)
    except StorageIOError as e:
        typer.echo(f"Storage error: {e}", err=True)
        raise typer.Exit(code=EXIT_IO_ERROR)

    raise typer.Exit(code=EXIT_SUCCESS)


if __name__ == "__main__":
    app()
