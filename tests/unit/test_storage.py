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
    TemplateNotFoundError,
    load_simulation,
    reset_simulation,
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
        (sim_path / "simulation.json").write_text("{invalid json", encoding="utf-8")

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


def create_test_template(tmp_path: Path, sim_id: str = "test-sim") -> Path:
    """Create a valid test template structure.

    Args:
        tmp_path: Temporary directory from pytest fixture.
        sim_id: Simulation identifier.

    Returns:
        Path to the base directory (containing simulations/_templates/).
    """
    base_path = tmp_path / "project"
    template_path = base_path / "simulations" / "_templates" / sim_id
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

    # character
    (template_path / "characters" / "héros.json").write_text(
        json.dumps(
            {
                "identity": {
                    "id": "héros",
                    "name": "Герой",
                    "description": "Тестовый персонаж с юникодом",
                },
                "state": {"location": "начало"},
                "memory": {"cells": [], "summary": ""},
            }
        ),
        encoding="utf-8",
    )

    # location
    (template_path / "locations" / "начало.json").write_text(
        json.dumps(
            {
                "identity": {
                    "id": "начало",
                    "name": "Начальная локация",
                    "description": "Место старта",
                    "connections": [],
                },
                "state": {"moment": ""},
            }
        ),
        encoding="utf-8",
    )

    # .gitkeep in logs
    (template_path / "logs" / ".gitkeep").write_text("", encoding="utf-8")

    return base_path


class TestResetSimulation:
    """Tests for reset_simulation function."""

    def test_reset_simulation_success(self, tmp_path: Path) -> None:
        """Resets simulation to template state."""
        base_path = create_test_template(tmp_path)
        sim_id = "test-sim"

        # Create modified working simulation
        working_path = base_path / "simulations" / sim_id
        working_path.mkdir(parents=True)
        (working_path / "characters").mkdir()
        (working_path / "locations").mkdir()
        (working_path / "logs").mkdir()

        # Modify simulation.json
        (working_path / "simulation.json").write_text(
            json.dumps(
                {
                    "id": sim_id,
                    "current_tick": 42,
                    "created_at": "2025-01-15T10:00:00Z",
                    "status": "paused",
                }
            ),
            encoding="utf-8",
        )

        # Add log file
        (working_path / "logs" / "tick_000001.md").write_text(
            "# Tick 1\nSome narrative", encoding="utf-8"
        )

        # Reset
        reset_simulation(sim_id, base_path)

        # Verify reset
        sim = load_simulation(working_path)
        assert sim.current_tick == 0
        assert sim.status == "paused"
        assert "héros" in sim.characters
        assert "начало" in sim.locations

        # Verify logs cleared
        logs_path = working_path / "logs"
        assert logs_path.exists()
        log_files = [f for f in logs_path.iterdir() if f.suffix == ".md"]
        assert len(log_files) == 0

    def test_reset_simulation_creates_target(self, tmp_path: Path) -> None:
        """Creates target simulation folder if it doesn't exist."""
        base_path = create_test_template(tmp_path)
        sim_id = "test-sim"

        # Ensure simulations folder exists but target doesn't
        (base_path / "simulations").mkdir(exist_ok=True)
        target_path = base_path / "simulations" / sim_id
        assert not target_path.exists()

        # Reset (should create target)
        reset_simulation(sim_id, base_path)

        # Verify target created
        assert target_path.exists()
        sim = load_simulation(target_path)
        assert sim.id == sim_id
        assert sim.current_tick == 0

    def test_reset_simulation_clears_logs(self, tmp_path: Path) -> None:
        """Clears logs folder contents after reset."""
        base_path = create_test_template(tmp_path)
        sim_id = "test-sim"

        # Create working simulation with logs
        working_path = base_path / "simulations" / sim_id
        working_path.mkdir(parents=True)
        (working_path / "logs").mkdir()
        (working_path / "logs" / "tick_000001.md").write_text("Log 1")
        (working_path / "logs" / "tick_000002.md").write_text("Log 2")
        (working_path / "logs" / "subdir").mkdir()
        (working_path / "logs" / "subdir" / "nested.txt").write_text("Nested")

        # Copy template simulation.json to make it valid
        import shutil

        template_path = base_path / "simulations" / "_templates" / sim_id
        shutil.copy(template_path / "simulation.json", working_path / "simulation.json")

        # Reset
        reset_simulation(sim_id, base_path)

        # Verify logs cleared
        logs_path = working_path / "logs"
        assert logs_path.exists()
        # Only .gitkeep should remain (copied from template)
        files = list(logs_path.iterdir())
        assert len(files) <= 1
        if files:
            assert files[0].name == ".gitkeep"

    def test_reset_simulation_template_not_found(self, tmp_path: Path) -> None:
        """Raises TemplateNotFoundError if template doesn't exist."""
        base_path = tmp_path / "project"
        (base_path / "simulations").mkdir(parents=True)

        with pytest.raises(TemplateNotFoundError) as exc_info:
            reset_simulation("nonexistent", base_path)

        assert exc_info.value.sim_id == "nonexistent"
        assert "nonexistent" in str(exc_info.value.template_path)

    def test_reset_simulation_creates_logs_if_missing(self, tmp_path: Path) -> None:
        """Creates logs folder if template doesn't have one."""
        base_path = tmp_path / "project"
        sim_id = "no-logs-template"
        template_path = base_path / "simulations" / "_templates" / sim_id
        template_path.mkdir(parents=True)
        (template_path / "characters").mkdir()
        (template_path / "locations").mkdir()
        # Note: no logs folder in template

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

        # Reset
        reset_simulation(sim_id, base_path)

        # Verify logs folder created
        target_path = base_path / "simulations" / sim_id
        logs_path = target_path / "logs"
        assert logs_path.exists()
        assert logs_path.is_dir()


class TestOpenaiRoundtrip:
    """Tests for _openai data preservation through roundtrip."""

    def test_roundtrip_preserves_openai_character(self, tmp_path: Path) -> None:
        """_openai data on character survives save/load cycle."""
        sim_path = create_test_simulation(tmp_path)

        # Load, add _openai via __pydantic_extra__, save
        sim = load_simulation(sim_path)
        bob = sim.characters["bob"]
        if bob.__pydantic_extra__ is None:
            object.__setattr__(bob, "__pydantic_extra__", {})
        bob.__pydantic_extra__["_openai"] = {
            "usage": {
                "total_tokens": 1000,
                "reasoning_tokens": 500,
                "cached_tokens": 100,
                "total_requests": 10,
            },
            "intention_chain": ["resp_001", "resp_002"],
        }
        save_simulation(sim_path, sim)

        # Reload and verify
        sim2 = load_simulation(sim_path)
        bob_openai = sim2.characters["bob"].model_extra.get("_openai")
        assert bob_openai is not None
        assert bob_openai["usage"]["total_tokens"] == 1000
        assert bob_openai["intention_chain"] == ["resp_001", "resp_002"]

    def test_roundtrip_preserves_openai_simulation(self, tmp_path: Path) -> None:
        """_openai data on simulation survives save/load cycle."""
        sim_path = create_test_simulation(tmp_path)

        # Load, add _openai via __pydantic_extra__, save
        sim = load_simulation(sim_path)
        if sim.__pydantic_extra__ is None:
            object.__setattr__(sim, "__pydantic_extra__", {})
        sim.__pydantic_extra__["_openai"] = {
            "total_tokens": 5000,
            "reasoning_tokens": 2000,
            "cached_tokens": 500,
            "total_requests": 25,
        }
        save_simulation(sim_path, sim)

        # Reload and verify
        sim2 = load_simulation(sim_path)
        sim_openai = sim2.model_extra.get("_openai")
        assert sim_openai is not None
        assert sim_openai["total_tokens"] == 5000
        assert sim_openai["total_requests"] == 25
