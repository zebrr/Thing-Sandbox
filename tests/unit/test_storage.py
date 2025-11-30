"""Unit tests for storage module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.storage import (
    Character,
    CharacterIdentity,
    CharacterMemory,
    CharacterState,
    InvalidDataError,
    Location,
    LocationIdentity,
    LocationState,
    Simulation,
    SimulationNotFoundError,
    StorageIOError,
    load_simulation,
    save_simulation,
)


def create_test_simulation(tmp_path: Path) -> Path:
    """Create a valid test simulation structure.

    Args:
        tmp_path: Temporary directory from pytest fixture.

    Returns:
        Path to the created simulation folder.
    """
    sim_path = tmp_path / "test-sim"
    sim_path.mkdir()
    (sim_path / "characters").mkdir()
    (sim_path / "locations").mkdir()

    # simulation.json
    (sim_path / "simulation.json").write_text(
        json.dumps(
            {
                "id": "test-sim",
                "current_tick": 0,
                "created_at": "2025-01-15T10:00:00Z",
                "status": "paused",
            }
        ),
        encoding="utf-8",
    )

    # character
    (sim_path / "characters" / "bob.json").write_text(
        json.dumps(
            {
                "identity": {
                    "id": "bob",
                    "name": "Боб",
                    "description": "Тестовый персонаж",
                },
                "state": {"location": "tavern"},
                "memory": {"cells": [], "summary": ""},
            }
        ),
        encoding="utf-8",
    )

    # location
    (sim_path / "locations" / "tavern.json").write_text(
        json.dumps(
            {
                "identity": {
                    "id": "tavern",
                    "name": "Таверна",
                    "description": "Уютное место",
                    "connections": [],
                },
                "state": {"moment": "Вечер"},
            }
        ),
        encoding="utf-8",
    )

    return sim_path


class TestLoadSimulation:
    """Tests for load_simulation function."""

    def test_load_simulation_success(self, tmp_path: Path) -> None:
        """Loads valid simulation with all data."""
        sim_path = create_test_simulation(tmp_path)

        sim = load_simulation(sim_path)

        assert sim.id == "test-sim"
        assert sim.current_tick == 0
        assert sim.status == "paused"
        assert "bob" in sim.characters
        assert sim.characters["bob"].identity.name == "Боб"
        assert "tavern" in sim.locations
        assert sim.locations["tavern"].identity.name == "Таверна"

    def test_load_simulation_not_found(self, tmp_path: Path) -> None:
        """Raises SimulationNotFoundError if folder doesn't exist."""
        missing_path = tmp_path / "nonexistent"

        with pytest.raises(SimulationNotFoundError) as exc_info:
            load_simulation(missing_path)

        assert exc_info.value.path == missing_path
        assert "not found" in str(exc_info.value).lower()

    def test_load_simulation_invalid_json(self, tmp_path: Path) -> None:
        """Raises InvalidDataError for broken JSON."""
        sim_path = tmp_path / "broken-sim"
        sim_path.mkdir()
        (sim_path / "simulation.json").write_text(
            "{invalid json", encoding="utf-8"
        )

        with pytest.raises(InvalidDataError) as exc_info:
            load_simulation(sim_path)

        assert "invalid json" in str(exc_info.value).lower()

    def test_load_simulation_validation_error(self, tmp_path: Path) -> None:
        """Raises InvalidDataError for invalid data structure."""
        sim_path = tmp_path / "invalid-sim"
        sim_path.mkdir()
        # Missing required field 'id'
        (sim_path / "simulation.json").write_text(
            json.dumps(
                {
                    "current_tick": 0,
                    "created_at": "2025-01-15T10:00:00Z",
                    "status": "paused",
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(InvalidDataError) as exc_info:
            load_simulation(sim_path)

        assert "validation" in str(exc_info.value).lower()

    def test_load_simulation_id_mismatch(self, tmp_path: Path) -> None:
        """Raises InvalidDataError if filename doesn't match identity.id."""
        sim_path = create_test_simulation(tmp_path)

        # Change bob.json to have id: "alice"
        (sim_path / "characters" / "bob.json").write_text(
            json.dumps(
                {
                    "identity": {
                        "id": "alice",  # Mismatch!
                        "name": "Alice",
                        "description": "Wrong id",
                    },
                    "state": {"location": "tavern"},
                    "memory": {"cells": [], "summary": ""},
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(InvalidDataError) as exc_info:
            load_simulation(sim_path)

        assert "mismatch" in str(exc_info.value).lower()
        assert "bob" in str(exc_info.value).lower()
        assert "alice" in str(exc_info.value).lower()

    def test_load_simulation_empty_characters(self, tmp_path: Path) -> None:
        """Returns empty dict if characters folder is empty."""
        sim_path = create_test_simulation(tmp_path)
        # Remove all character files
        for f in (sim_path / "characters").iterdir():
            f.unlink()

        sim = load_simulation(sim_path)

        assert sim.characters == {}

    def test_load_simulation_empty_locations(self, tmp_path: Path) -> None:
        """Returns empty dict if locations folder is empty."""
        sim_path = create_test_simulation(tmp_path)
        # Remove all location files
        for f in (sim_path / "locations").iterdir():
            f.unlink()

        sim = load_simulation(sim_path)

        assert sim.locations == {}

    def test_load_simulation_missing_folders(self, tmp_path: Path) -> None:
        """Returns empty dicts if characters/locations folders don't exist."""
        sim_path = tmp_path / "minimal-sim"
        sim_path.mkdir()
        (sim_path / "simulation.json").write_text(
            json.dumps(
                {
                    "id": "minimal-sim",
                    "current_tick": 0,
                    "created_at": "2025-01-15T10:00:00Z",
                    "status": "paused",
                }
            ),
            encoding="utf-8",
        )

        sim = load_simulation(sim_path)

        assert sim.characters == {}
        assert sim.locations == {}

    def test_load_simulation_ignores_non_json(self, tmp_path: Path) -> None:
        """Non-JSON files are ignored."""
        sim_path = create_test_simulation(tmp_path)
        # Add non-JSON files
        (sim_path / "characters" / "readme.txt").write_text("Ignore me")
        (sim_path / "characters" / "notes.md").write_text("# Notes")
        (sim_path / "locations" / ".gitkeep").write_text("")

        sim = load_simulation(sim_path)

        # Only bob should be loaded
        assert len(sim.characters) == 1
        assert "bob" in sim.characters
        assert len(sim.locations) == 1
        assert "tavern" in sim.locations

    def test_load_simulation_extra_fields(self, tmp_path: Path) -> None:
        """Extra fields in JSON are preserved in models."""
        sim_path = tmp_path / "extra-sim"
        sim_path.mkdir()
        (sim_path / "characters").mkdir()
        (sim_path / "locations").mkdir()

        (sim_path / "simulation.json").write_text(
            json.dumps(
                {
                    "id": "extra-sim",
                    "current_tick": 0,
                    "created_at": "2025-01-15T10:00:00Z",
                    "status": "paused",
                    "custom_field": "custom_value",
                }
            ),
            encoding="utf-8",
        )

        (sim_path / "characters" / "hero.json").write_text(
            json.dumps(
                {
                    "identity": {
                        "id": "hero",
                        "name": "Hero",
                        "description": "The protagonist",
                        "extra_identity_field": 42,
                    },
                    "state": {
                        "location": "start",
                        "custom_state": {"nested": "data"},
                    },
                    "memory": {
                        "cells": [],
                        "summary": "",
                        "extra_memory": True,
                    },
                }
            ),
            encoding="utf-8",
        )

        sim = load_simulation(sim_path)

        # Check extra fields are preserved
        assert sim.model_extra.get("custom_field") == "custom_value"
        hero = sim.characters["hero"]
        assert hero.identity.model_extra.get("extra_identity_field") == 42
        assert hero.state.model_extra.get("custom_state") == {"nested": "data"}
        assert hero.memory.model_extra.get("extra_memory") is True


class TestSaveSimulation:
    """Tests for save_simulation function."""

    def test_save_simulation_success(self, tmp_path: Path) -> None:
        """All files are written correctly."""
        sim_path = tmp_path / "save-test"
        sim_path.mkdir()
        (sim_path / "characters").mkdir()
        (sim_path / "locations").mkdir()

        # Create simulation in memory
        sim = Simulation(
            id="save-test",
            current_tick=5,
            created_at="2025-01-15T10:00:00Z",
            status="paused",
            characters={
                "wizard": Character(
                    identity=CharacterIdentity(
                        id="wizard",
                        name="Волшебник",
                        description="Могущественный маг",
                    ),
                    state=CharacterState(location="tower"),
                    memory=CharacterMemory(cells=[], summary=""),
                )
            },
            locations={
                "tower": Location(
                    identity=LocationIdentity(
                        id="tower",
                        name="Башня",
                        description="Высокая башня",
                        connections=[],
                    ),
                    state=LocationState(moment="Ночь"),
                )
            },
        )

        save_simulation(sim_path, sim)

        # Verify files exist and contain correct data
        sim_file = sim_path / "simulation.json"
        assert sim_file.exists()
        sim_data = json.loads(sim_file.read_text(encoding="utf-8"))
        assert sim_data["id"] == "save-test"
        assert sim_data["current_tick"] == 5

        char_file = sim_path / "characters" / "wizard.json"
        assert char_file.exists()
        char_data = json.loads(char_file.read_text(encoding="utf-8"))
        assert char_data["identity"]["name"] == "Волшебник"

        loc_file = sim_path / "locations" / "tower.json"
        assert loc_file.exists()
        loc_data = json.loads(loc_file.read_text(encoding="utf-8"))
        assert loc_data["identity"]["name"] == "Башня"

    def test_save_simulation_io_error(self, tmp_path: Path) -> None:
        """Raises StorageIOError on write failure."""
        sim_path = tmp_path / "io-error-test"
        sim_path.mkdir()
        (sim_path / "characters").mkdir()
        (sim_path / "locations").mkdir()

        sim = Simulation(
            id="io-error-test",
            current_tick=0,
            created_at="2025-01-15T10:00:00Z",
            status="paused",
        )

        # Mock open to raise OSError
        with patch("builtins.open", side_effect=OSError("Disk full")):
            with pytest.raises(StorageIOError) as exc_info:
                save_simulation(sim_path, sim)

            assert exc_info.value.cause is not None

    def test_save_simulation_preserves_extra_fields(self, tmp_path: Path) -> None:
        """Extra fields are not lost during roundtrip."""
        sim_path = tmp_path / "extra-roundtrip"
        sim_path.mkdir()
        (sim_path / "characters").mkdir()
        (sim_path / "locations").mkdir()

        # Create simulation with extra fields
        sim = Simulation(
            id="extra-roundtrip",
            current_tick=0,
            created_at="2025-01-15T10:00:00Z",
            status="paused",
            characters={
                "test": Character(
                    identity=CharacterIdentity(
                        id="test",
                        name="Test",
                        description="Test char",
                        extra_field="preserved",  # type: ignore[call-arg]
                    ),
                    state=CharacterState(
                        location="here",
                        custom_data={"key": "value"},  # type: ignore[call-arg]
                    ),
                    memory=CharacterMemory(),
                )
            },
            locations={},
        )

        save_simulation(sim_path, sim)

        # Reload and check extra fields
        char_file = sim_path / "characters" / "test.json"
        char_data = json.loads(char_file.read_text(encoding="utf-8"))
        assert char_data["identity"]["extra_field"] == "preserved"
        assert char_data["state"]["custom_data"] == {"key": "value"}


class TestRoundtrip:
    """Tests for load → modify → save → load cycle."""

    def test_roundtrip(self, tmp_path: Path) -> None:
        """Data survives load → modify → save → load cycle."""
        sim_path = create_test_simulation(tmp_path)

        # Load
        sim1 = load_simulation(sim_path)
        original_tick = sim1.current_tick

        # Modify
        sim1.current_tick += 1
        sim1.status = "running"
        sim1.characters["bob"].state.location = "forest"

        # Save
        save_simulation(sim_path, sim1)

        # Load again
        sim2 = load_simulation(sim_path)

        # Verify changes persisted
        assert sim2.current_tick == original_tick + 1
        assert sim2.status == "running"
        assert sim2.characters["bob"].state.location == "forest"
        # Original data preserved
        assert sim2.id == "test-sim"
        assert sim2.characters["bob"].identity.name == "Боб"
        assert "tavern" in sim2.locations
