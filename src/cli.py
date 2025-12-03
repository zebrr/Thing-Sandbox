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

import typer

from src.config import Config, ConfigError
from src.narrators import ConsoleNarrator
from src.runner import PhaseError, SimulationBusyError, TickRunner
from src.utils.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_IO_ERROR,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
)
from src.utils.storage import (
    InvalidDataError,
    SimulationNotFoundError,
    StorageIOError,
    TemplateNotFoundError,
    load_simulation,
    reset_simulation,
)

app = typer.Typer(
    name="thing-sandbox",
    help="Thing' Sandbox - LLM-driven text simulation",
)


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

    try:
        asyncio.run(_run_tick(config, sim_id))
    except SimulationNotFoundError:
        typer.echo(f"Simulation '{sim_id}' not found", err=True)
        raise typer.Exit(code=EXIT_INPUT_ERROR)
    except InvalidDataError as e:
        typer.echo(f"Invalid simulation data: {e}", err=True)
        raise typer.Exit(code=EXIT_INPUT_ERROR)
    except SimulationBusyError:
        typer.echo(f"Simulation '{sim_id}' is busy (status: running)", err=True)
        raise typer.Exit(code=EXIT_RUNTIME_ERROR)
    except PhaseError as e:
        typer.echo(f"Phase failed: {e}", err=True)
        raise typer.Exit(code=EXIT_RUNTIME_ERROR)
    except StorageIOError as e:
        typer.echo(f"Storage error: {e}", err=True)
        raise typer.Exit(code=EXIT_IO_ERROR)


async def _run_tick(config: Config, sim_id: str) -> None:
    """Execute tick asynchronously.

    Args:
        config: Application configuration.
        sim_id: Simulation identifier.
    """
    narrators = [ConsoleNarrator()]
    runner = TickRunner(config, narrators)

    result = await runner.run_tick(sim_id)

    typer.echo(f"[{sim_id}] Tick {result.tick_number} completed.")


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

    sim_path = config._project_root / "simulations" / sim_id

    try:
        simulation = load_simulation(sim_path)
    except SimulationNotFoundError:
        typer.echo(f"Error: Simulation '{sim_id}' not found", err=True)
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
        reset_simulation(sim_id, config._project_root)
        typer.echo(f"[{sim_id}] Reset to template.")
    except TemplateNotFoundError:
        typer.echo(f"Error: Template for '{sim_id}' not found", err=True)
        raise typer.Exit(code=EXIT_INPUT_ERROR)
    except StorageIOError as e:
        typer.echo(f"Storage error: {e}", err=True)
        raise typer.Exit(code=EXIT_IO_ERROR)

    raise typer.Exit(code=EXIT_SUCCESS)


if __name__ == "__main__":
    app()
