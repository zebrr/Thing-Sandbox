"""Integration tests for skeleton system (Runner + CLI + Narrators).

These tests verify the integration between Runner, CLI, and Narrators
without making real LLM calls. Phase 1 is mocked to return idle intentions.
"""

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.config import Config
from src.narrators import ConsoleNarrator
from src.phases.common import PhaseResult
from src.phases.phase1 import IntentionResponse
from src.runner import TickRunner
from src.utils.storage import SimulationNotFoundError, load_simulation


@pytest.fixture
def temp_demo_sim(tmp_path: Path, project_root: Path) -> Path:
    """Copy demo-sim to a temporary directory for isolated testing.

    Returns path to the temporary simulation folder.
    """
    source = project_root / "simulations" / "demo-sim"
    dest = tmp_path / "simulations" / "demo-sim"

    # Create simulations directory and copy demo-sim
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)

    return dest


@pytest.fixture
def temp_config(tmp_path: Path, project_root: Path) -> Config:
    """Create config pointing to temporary project root.

    Copies config.toml and .env to temp location.
    """
    # Copy config.toml
    config_source = project_root / "config.toml"
    config_dest = tmp_path / "config.toml"
    shutil.copy(config_source, config_dest)

    # Copy .env if exists
    env_source = project_root / ".env"
    if env_source.exists():
        env_dest = tmp_path / ".env"
        shutil.copy(env_source, env_dest)

    # Copy src/prompts (needed for config.resolve_prompt)
    prompts_source = project_root / "src" / "prompts"
    prompts_dest = tmp_path / "src" / "prompts"
    if prompts_source.exists():
        prompts_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(prompts_source, prompts_dest)

    return Config.load(config_path=config_dest, project_root=tmp_path)


def _mock_phase1_result(simulation):
    """Create mock Phase 1 result with idle intentions for all characters."""
    intentions = {char_id: IntentionResponse(intention="idle") for char_id in simulation.characters}
    return PhaseResult(success=True, data=intentions)


@pytest.mark.asyncio
async def test_run_tick_increments_current_tick(temp_demo_sim: Path, temp_config: Config) -> None:
    """Running a tick increments current_tick from 0 to 1."""
    # Verify initial state
    sim_before = load_simulation(temp_demo_sim)
    assert sim_before.current_tick == 0
    assert sim_before.status == "paused"

    # Mock Phase 1 to avoid LLM calls
    async def mock_execute(simulation, config, llm_client):
        return _mock_phase1_result(simulation)

    with (
        patch("src.runner.execute_phase1", mock_execute),
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}),
    ):
        runner = TickRunner(temp_config, [])
        result = await runner.run_tick("demo-sim")

    # Verify result
    assert result.success is True
    assert result.tick_number == 1

    # Reload from disk and verify
    sim_after = load_simulation(temp_demo_sim)
    assert sim_after.current_tick == 1
    assert sim_after.status == "paused"


@pytest.mark.asyncio
async def test_run_tick_returns_narratives(temp_demo_sim: Path, temp_config: Config) -> None:
    """Running a tick returns narratives for all locations."""
    sim = load_simulation(temp_demo_sim)
    location_ids = list(sim.locations.keys())

    async def mock_execute(simulation, config, llm_client):
        return _mock_phase1_result(simulation)

    with (
        patch("src.runner.execute_phase1", mock_execute),
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}),
    ):
        runner = TickRunner(temp_config, [])
        result = await runner.run_tick("demo-sim")

    assert result.success is True
    assert isinstance(result.narratives, dict)

    # Should have narrative for each location
    for loc_id in location_ids:
        assert loc_id in result.narratives
        # Stubs return "[Stub]..." text
        assert result.narratives[loc_id]
        assert "[Stub]" in result.narratives[loc_id]

    # Should have location names
    assert isinstance(result.location_names, dict)
    for loc_id in location_ids:
        assert loc_id in result.location_names
        # Names should be non-empty strings
        assert result.location_names[loc_id]


@pytest.mark.asyncio
async def test_run_tick_simulation_not_found(temp_config: Config) -> None:
    """Running tick on non-existent simulation raises SimulationNotFoundError."""
    runner = TickRunner(temp_config, [])

    with pytest.raises(SimulationNotFoundError):
        await runner.run_tick("nonexistent-sim")


@pytest.mark.asyncio
async def test_run_tick_calls_narrators(temp_demo_sim: Path, temp_config: Config) -> None:
    """Narrators are called after successful tick."""
    captured_results: list = []

    class MockNarrator:
        def output(self, result):
            captured_results.append(result)

    async def mock_execute(simulation, config, llm_client):
        return _mock_phase1_result(simulation)

    with (
        patch("src.runner.execute_phase1", mock_execute),
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}),
    ):
        runner = TickRunner(temp_config, [MockNarrator()])
        result = await runner.run_tick("demo-sim")

    assert len(captured_results) == 1
    assert captured_results[0] is result


def test_status_command_output(
    temp_demo_sim: Path, temp_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Status command outputs correct format."""
    # Monkeypatch Config.load to return our temp config
    monkeypatch.setattr("src.cli.Config.load", lambda: temp_config)

    runner = CliRunner()
    result = runner.invoke(app, ["status", "demo-sim"])

    assert result.exit_code == 0
    output = result.stdout

    # Check expected content
    assert "demo-sim" in output
    assert "tick 0" in output
    assert "2 characters" in output
    assert "2 locations" in output
    assert "status: paused" in output


def test_status_command_not_found(temp_config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    """Status command returns exit code 2 for non-existent simulation."""
    monkeypatch.setattr("src.cli.Config.load", lambda: temp_config)

    runner = CliRunner()
    result = runner.invoke(app, ["status", "nonexistent-sim"])

    assert result.exit_code == 2
    # Error output goes to stderr, but CliRunner mixes it into output
    assert "not found" in result.output


def test_console_narrator_output(capsys: pytest.CaptureFixture) -> None:
    """ConsoleNarrator prints formatted output."""
    from src.runner import TickResult

    narrator = ConsoleNarrator()
    result = TickResult(
        sim_id="test-sim",
        tick_number=42,
        narratives={
            "tavern": "Bob enters the tavern.",
            "forest": "",  # Empty narrative
        },
        location_names={
            "tavern": "The Rusty Tankard",
            "forest": "Dark Forest",
        },
        success=True,
    )

    narrator.output(result)

    captured = capsys.readouterr()
    output = captured.out

    # Check header
    assert "═" in output
    assert "TICK 42" in output

    # Check locations
    assert "--- The Rusty Tankard ---" in output
    assert "Bob enters the tavern." in output

    assert "--- Dark Forest ---" in output
    assert "[No narrative]" in output


def test_run_command_success(
    temp_demo_sim: Path, temp_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run command completes successfully and shows completion message."""
    monkeypatch.setattr("src.cli.Config.load", lambda: temp_config)

    # Mock Phase 1 to avoid LLM calls
    async def mock_execute(simulation, config, llm_client):
        return _mock_phase1_result(simulation)

    with (
        patch("src.runner.execute_phase1", mock_execute),
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}),
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["run", "demo-sim"])

    # Should exit successfully
    assert result.exit_code == 0

    # Should show completion message
    assert "[demo-sim] Tick 1 completed." in result.stdout


def test_run_command_not_found(temp_config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run command returns exit code 2 for non-existent simulation."""
    monkeypatch.setattr("src.cli.Config.load", lambda: temp_config)

    runner = CliRunner()
    result = runner.invoke(app, ["run", "nonexistent-sim"])

    assert result.exit_code == 2
    # Error output goes to stderr, but CliRunner mixes it into output
    assert "not found" in result.output
