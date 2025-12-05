"""Unit tests for CLI module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli import app
from src.utils.exit_codes import EXIT_INPUT_ERROR, EXIT_IO_ERROR, EXIT_SUCCESS

runner = CliRunner()


def create_test_template(tmp_path: Path, sim_id: str = "test-sim") -> Path:
    """Create a valid test template structure.

    Args:
        tmp_path: Temporary directory from pytest fixture.
        sim_id: Simulation identifier.

    Returns:
        Path to the base directory (containing simulations/_templates/).
    """
    template_path = tmp_path / "simulations" / "_templates" / sim_id
    template_path.mkdir(parents=True)
    (template_path / "characters").mkdir()
    (template_path / "locations").mkdir()
    (template_path / "logs").mkdir()

    # simulation.json
    (template_path / "simulation.json").write_text(
        json.dumps(
            {
                "id": sim_id,
                "current_tick": 0,
                "created_at": "2025-01-15T10:00:00Z",
                "status": "paused",
            }
        ),
        encoding="utf-8",
    )

    # .gitkeep in logs
    (template_path / "logs" / ".gitkeep").write_text("", encoding="utf-8")

    return tmp_path


class TestResetCommand:
    """Tests for reset CLI command."""

    def test_reset_command_success(self, tmp_path: Path) -> None:
        """Reset command exits with code 0 and prints success message."""
        base_path = create_test_template(tmp_path)
        sim_id = "test-sim"

        # Create mock config that returns our test path
        mock_config = MagicMock()
        mock_config._project_root = base_path

        with patch("src.cli.Config.load", return_value=mock_config):
            result = runner.invoke(app, ["reset", sim_id])

        assert result.exit_code == EXIT_SUCCESS
        assert f"[{sim_id}] Reset to template." in result.stdout

        # Verify simulation was created
        sim_path = base_path / "simulations" / sim_id
        assert sim_path.exists()

    def test_reset_command_template_not_found(self, tmp_path: Path) -> None:
        """Reset command exits with code 2 when template doesn't exist."""
        base_path = tmp_path
        (base_path / "simulations").mkdir(parents=True)
        sim_id = "nonexistent"

        mock_config = MagicMock()
        mock_config._project_root = base_path

        with patch("src.cli.Config.load", return_value=mock_config):
            result = runner.invoke(app, ["reset", sim_id])

        assert result.exit_code == EXIT_INPUT_ERROR
        assert f"Template for '{sim_id}' not found" in result.output

    def test_reset_command_storage_error(self, tmp_path: Path) -> None:
        """Reset command exits with code 5 on storage error."""
        from src.utils.storage import StorageIOError

        mock_config = MagicMock()
        mock_config._project_root = tmp_path

        with (
            patch("src.cli.Config.load", return_value=mock_config),
            patch(
                "src.cli.reset_simulation",
                side_effect=StorageIOError("Disk full", tmp_path / "simulations" / "test", None),
            ),
        ):
            result = runner.invoke(app, ["reset", "test"])

        assert result.exit_code == EXIT_IO_ERROR
        assert "Storage error" in result.output
