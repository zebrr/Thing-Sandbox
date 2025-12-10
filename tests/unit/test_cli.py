"""Unit tests for CLI module."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
        mock_config.project_root = base_path

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
        mock_config.project_root = base_path

        with patch("src.cli.Config.load", return_value=mock_config):
            result = runner.invoke(app, ["reset", sim_id])

        assert result.exit_code == EXIT_INPUT_ERROR
        assert f"Template for '{sim_id}' not found" in result.output

    def test_reset_command_storage_error(self, tmp_path: Path) -> None:
        """Reset command exits with code 5 on storage error."""
        from src.utils.storage import StorageIOError

        mock_config = MagicMock()
        mock_config.project_root = tmp_path

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


class TestTelegramIntegration:
    """Tests for TelegramNarrator integration in CLI.

    These tests directly test the _run_tick async function to verify
    TelegramNarrator creation logic.
    """

    @pytest.mark.asyncio
    async def test_cli_creates_telegram_narrator(self) -> None:
        """TelegramNarrator is created when enabled, mode != none, and token present."""
        from src.cli import _run_tick
        from src.config import (
            ConsoleOutputConfig,
            FileOutputConfig,
            OutputConfig,
            TelegramOutputConfig,
        )

        mock_config = MagicMock()
        mock_config.telegram_bot_token = "test-token-123"

        mock_simulation = MagicMock()
        mock_sim_path = Path("/fake/path")
        mock_output_config = OutputConfig(
            console=ConsoleOutputConfig(show_narratives=True),
            file=FileOutputConfig(enabled=True),
            telegram=TelegramOutputConfig(
                enabled=True,
                chat_id="-100123456",
                mode="full",
                group_intentions=True,
                group_narratives=True,
            ),
        )

        with (
            patch("src.cli.TelegramClient") as mock_client_class,
            patch("src.cli.TelegramNarrator") as mock_narrator_class,
            patch("src.cli.TickRunner") as mock_runner_class,
        ):
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_tick = AsyncMock()
            mock_runner_class.return_value = mock_runner_instance

            await _run_tick(mock_config, mock_simulation, mock_sim_path, mock_output_config)

            # TelegramClient should be created with token
            mock_client_class.assert_called_once_with("test-token-123")

            # TelegramNarrator should be created with correct params
            mock_narrator_class.assert_called_once_with(
                client=mock_client_class.return_value,
                chat_id="-100123456",
                mode="full",
                group_intentions=True,
                group_narratives=True,
            )

            # Runner should receive 2 narrators (Console + Telegram)
            call_args = mock_runner_class.call_args
            narrators_list = call_args[0][1]  # Second positional arg
            assert len(narrators_list) == 2

    @pytest.mark.asyncio
    async def test_cli_warns_no_token(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Warning is shown when Telegram enabled but token not set."""
        from src.cli import _run_tick
        from src.config import (
            ConsoleOutputConfig,
            FileOutputConfig,
            OutputConfig,
            TelegramOutputConfig,
        )

        mock_config = MagicMock()
        mock_config.telegram_bot_token = None  # No token

        mock_simulation = MagicMock()
        mock_sim_path = Path("/fake/path")
        mock_output_config = OutputConfig(
            console=ConsoleOutputConfig(show_narratives=True),
            file=FileOutputConfig(enabled=True),
            telegram=TelegramOutputConfig(
                enabled=True,
                chat_id="-100123456",
                mode="full",
            ),
        )

        with (
            patch("src.cli.TelegramClient") as mock_client_class,
            patch("src.cli.TelegramNarrator") as mock_narrator_class,
            patch("src.cli.TickRunner") as mock_runner_class,
            patch("src.cli.typer.echo") as mock_echo,
        ):
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_tick = AsyncMock()
            mock_runner_class.return_value = mock_runner_instance

            await _run_tick(mock_config, mock_simulation, mock_sim_path, mock_output_config)

            # Warning should be called with err=True
            mock_echo.assert_called_once_with(
                "Telegram enabled but TELEGRAM_BOT_TOKEN not set", err=True
            )

            # TelegramClient should NOT be created
            mock_client_class.assert_not_called()

            # TelegramNarrator should NOT be created
            mock_narrator_class.assert_not_called()

            # Runner should receive only 1 narrator (Console only)
            call_args = mock_runner_class.call_args
            narrators_list = call_args[0][1]
            assert len(narrators_list) == 1

    @pytest.mark.asyncio
    async def test_cli_telegram_disabled(self) -> None:
        """TelegramNarrator is NOT created when telegram.enabled=False."""
        from src.cli import _run_tick
        from src.config import (
            ConsoleOutputConfig,
            FileOutputConfig,
            OutputConfig,
            TelegramOutputConfig,
        )

        mock_config = MagicMock()
        mock_config.telegram_bot_token = "test-token-123"

        mock_simulation = MagicMock()
        mock_sim_path = Path("/fake/path")
        mock_output_config = OutputConfig(
            console=ConsoleOutputConfig(show_narratives=True),
            file=FileOutputConfig(enabled=True),
            telegram=TelegramOutputConfig(
                enabled=False,  # Disabled
                chat_id="-100123456",
                mode="full",
            ),
        )

        with (
            patch("src.cli.TelegramClient") as mock_client_class,
            patch("src.cli.TelegramNarrator") as mock_narrator_class,
            patch("src.cli.TickRunner") as mock_runner_class,
            patch("src.cli.typer.echo") as mock_echo,
        ):
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_tick = AsyncMock()
            mock_runner_class.return_value = mock_runner_instance

            await _run_tick(mock_config, mock_simulation, mock_sim_path, mock_output_config)

            # No warning should be shown
            mock_echo.assert_not_called()

            # TelegramClient should NOT be created
            mock_client_class.assert_not_called()

            # TelegramNarrator should NOT be created
            mock_narrator_class.assert_not_called()

            # Runner should receive only 1 narrator (Console only)
            call_args = mock_runner_class.call_args
            narrators_list = call_args[0][1]
            assert len(narrators_list) == 1

    @pytest.mark.asyncio
    async def test_cli_telegram_mode_none(self) -> None:
        """TelegramNarrator is NOT created when telegram.mode='none'."""
        from src.cli import _run_tick
        from src.config import (
            ConsoleOutputConfig,
            FileOutputConfig,
            OutputConfig,
            TelegramOutputConfig,
        )

        mock_config = MagicMock()
        mock_config.telegram_bot_token = "test-token-123"

        mock_simulation = MagicMock()
        mock_sim_path = Path("/fake/path")
        mock_output_config = OutputConfig(
            console=ConsoleOutputConfig(show_narratives=True),
            file=FileOutputConfig(enabled=True),
            telegram=TelegramOutputConfig(
                enabled=True,
                chat_id="-100123456",
                mode="none",  # Mode is none
            ),
        )

        with (
            patch("src.cli.TelegramClient") as mock_client_class,
            patch("src.cli.TelegramNarrator") as mock_narrator_class,
            patch("src.cli.TickRunner") as mock_runner_class,
            patch("src.cli.typer.echo") as mock_echo,
        ):
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_tick = AsyncMock()
            mock_runner_class.return_value = mock_runner_instance

            await _run_tick(mock_config, mock_simulation, mock_sim_path, mock_output_config)

            # No warning should be shown
            mock_echo.assert_not_called()

            # TelegramClient should NOT be created
            mock_client_class.assert_not_called()

            # TelegramNarrator should NOT be created
            mock_narrator_class.assert_not_called()

            # Runner should receive only 1 narrator (Console only)
            call_args = mock_runner_class.call_args
            narrators_list = call_args[0][1]
            assert len(narrators_list) == 1
