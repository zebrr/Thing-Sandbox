"""Storage module for Thing' Sandbox.

Loads and saves simulation state — simulation metadata, characters, and locations.
Validates data using Pydantic models. Provides atomic save operations at tick level.

Example:
    >>> from pathlib import Path
    >>> from src.utils.storage import load_simulation, save_simulation
    >>> sim = load_simulation(Path("simulations/my-sim"))
    >>> sim.current_tick += 1
    >>> save_simulation(Path("simulations/my-sim"), sim)
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class SimulationNotFoundError(Exception):
    """Simulation folder doesn't exist.

    Example:
        >>> raise SimulationNotFoundError(Path("simulations/missing"))
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Simulation not found: {path}")


class InvalidDataError(Exception):
    """JSON parsing or validation failed.

    Example:
        >>> raise InvalidDataError("Invalid JSON syntax", Path("file.json"))
    """

    def __init__(self, message: str, path: Path | None = None) -> None:
        self.path = path
        super().__init__(message)


class StorageIOError(Exception):
    """File read/write failed.

    Example:
        >>> raise StorageIOError("Cannot write file", Path("file.json"), cause=err)
    """

    def __init__(self, message: str, path: Path, cause: Exception | None = None) -> None:
        self.path = path
        self.cause = cause
        super().__init__(message)


class TemplateNotFoundError(Exception):
    """Template for simulation doesn't exist.

    Example:
        >>> raise TemplateNotFoundError("demo-sim", Path("simulations/_templates/demo-sim"))
    """

    def __init__(self, sim_id: str, template_path: Path) -> None:
        self.sim_id = sim_id
        self.template_path = template_path
        super().__init__(f"Template not found for '{sim_id}': {template_path}")


# =============================================================================
# Character Models
# =============================================================================


class CharacterIdentity(BaseModel):
    """Static part of character — who the character is.

    Example:
        >>> identity = CharacterIdentity(id="bob", name="Bob", description="A wizard")
    """

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str
    triggers: str | None = None


class MemoryCell(BaseModel):
    """Single memory entry from a specific tick.

    Example:
        >>> cell = MemoryCell(tick=5, text="I saw a dragon")
    """

    model_config = ConfigDict(extra="allow")

    tick: int
    text: str


class CharacterMemory(BaseModel):
    """Character's subjective memories — FIFO queue plus summary.

    Example:
        >>> memory = CharacterMemory(cells=[], summary="")
    """

    model_config = ConfigDict(extra="allow")

    cells: list[MemoryCell] = []
    summary: str = ""


class CharacterState(BaseModel):
    """Dynamic part of character — current situation.

    Example:
        >>> state = CharacterState(location="tavern")
    """

    model_config = ConfigDict(extra="allow")

    location: str
    internal_state: str | None = None
    external_intent: str | None = None


class Character(BaseModel):
    """Autonomous entity controlled by LLM.

    Example:
        >>> char = Character(
        ...     identity=CharacterIdentity(id="bob", name="Bob", description="A wizard"),
        ...     state=CharacterState(location="tavern"),
        ...     memory=CharacterMemory()
        ... )
    """

    model_config = ConfigDict(extra="allow")

    identity: CharacterIdentity
    state: CharacterState
    memory: CharacterMemory


# =============================================================================
# Location Models
# =============================================================================


class LocationConnection(BaseModel):
    """Connection to another location.

    Example:
        >>> conn = LocationConnection(location_id="forest", description="A path north")
    """

    model_config = ConfigDict(extra="allow")

    location_id: str
    description: str


class LocationIdentity(BaseModel):
    """Static part of location — what this place is.

    Example:
        >>> identity = LocationIdentity(
        ...     id="tavern", name="Tavern", description="A cozy place", connections=[]
        ... )
    """

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str
    connections: list[LocationConnection] = []


class LocationState(BaseModel):
    """Dynamic part of location — current situation.

    Example:
        >>> state = LocationState(moment="Evening, fire crackling")
    """

    model_config = ConfigDict(extra="allow")

    moment: str = ""


class Location(BaseModel):
    """A place in the world where characters and events exist.

    Example:
        >>> loc = Location(
        ...     identity=LocationIdentity(
        ...         id="tavern", name="Tavern", description="Cozy", connections=[]
        ...     ),
        ...     state=LocationState(moment="Evening")
        ... )
    """

    model_config = ConfigDict(extra="allow")

    identity: LocationIdentity
    state: LocationState


# =============================================================================
# Simulation Model
# =============================================================================


class Simulation(BaseModel):
    """Main container for simulation state.

    Example:
        >>> from datetime import datetime
        >>> sim = Simulation(
        ...     id="my-sim",
        ...     current_tick=0,
        ...     created_at=datetime.now(),
        ...     status="paused"
        ... )
    """

    model_config = ConfigDict(extra="allow")

    id: str
    current_tick: int = 0
    created_at: datetime
    status: Literal["running", "paused"] = "paused"
    characters: dict[str, Character] = {}
    locations: dict[str, Location] = {}


# =============================================================================
# Functions
# =============================================================================


def load_simulation(path: Path) -> Simulation:
    """Load complete simulation state from disk.

    Args:
        path: Path to simulation folder (e.g., Path("simulations/sim-01")).

    Returns:
        Simulation instance with all characters and locations loaded.

    Raises:
        SimulationNotFoundError: Simulation folder doesn't exist.
        InvalidDataError: JSON parsing failed, validation failed, or id mismatch.
        StorageIOError: File read failed.

    Example:
        >>> sim = load_simulation(Path("simulations/my-sim"))
        >>> print(sim.current_tick)
    """
    # Check if simulation folder exists
    if not path.exists():
        logger.error("Simulation folder not found: %s", path)
        raise SimulationNotFoundError(path)

    if not path.is_dir():
        logger.error("Path is not a directory: %s", path)
        raise SimulationNotFoundError(path)

    # Load simulation.json
    sim_file = path / "simulation.json"
    if not sim_file.exists():
        logger.error("simulation.json not found: %s", sim_file)
        raise InvalidDataError(f"simulation.json not found in {path}", sim_file)

    try:
        with open(sim_file, encoding="utf-8") as f:
            sim_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", sim_file, e)
        raise InvalidDataError(f"Invalid JSON in {sim_file}: {e}", sim_file)
    except OSError as e:
        logger.error("Cannot read %s: %s", sim_file, e)
        raise StorageIOError(f"Cannot read {sim_file}: {e}", sim_file, e)

    # Load characters
    characters: dict[str, Character] = {}
    chars_dir = path / "characters"
    if chars_dir.exists() and chars_dir.is_dir():
        characters = cast(dict[str, Character], _load_entities(chars_dir, Character, "character"))

    # Load locations
    locations: dict[str, Location] = {}
    locs_dir = path / "locations"
    if locs_dir.exists() and locs_dir.is_dir():
        locations = cast(dict[str, Location], _load_entities(locs_dir, Location, "location"))

    # Build Simulation object
    sim_data["characters"] = characters
    sim_data["locations"] = locations

    try:
        simulation = Simulation.model_validate(sim_data)
    except ValidationError as e:
        logger.error("Validation error in simulation.json: %s", e)
        raise InvalidDataError(f"Validation error in {sim_file}: {e}", sim_file)

    logger.debug(
        "Loaded simulation %s: tick=%d, %d characters, %d locations",
        simulation.id,
        simulation.current_tick,
        len(simulation.characters),
        len(simulation.locations),
    )

    return simulation


def _load_entities(
    directory: Path,
    model_class: type[Character] | type[Location],
    entity_type: str,
) -> dict[str, Character] | dict[str, Location]:
    """Load all entities from a directory.

    Args:
        directory: Directory containing JSON files.
        model_class: Pydantic model class to use for validation.
        entity_type: Type name for error messages ("character" or "location").

    Returns:
        Dictionary mapping entity id to entity instance.

    Raises:
        InvalidDataError: JSON parsing or validation failed.
        StorageIOError: File read failed.
    """
    entities: dict[str, Character | Location] = {}

    for file_path in directory.iterdir():
        # Skip non-JSON files
        if not file_path.suffix == ".json":
            continue

        # Expected id from filename
        expected_id = file_path.stem

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", file_path, e)
            raise InvalidDataError(f"Invalid JSON in {file_path}: {e}", file_path)
        except OSError as e:
            logger.error("Cannot read %s: %s", file_path, e)
            raise StorageIOError(f"Cannot read {file_path}: {e}", file_path, e)

        try:
            entity = model_class.model_validate(data)
        except ValidationError as e:
            logger.error("Validation error in %s: %s", file_path, e)
            raise InvalidDataError(f"Validation error in {file_path}: {e}", file_path)

        # Check id consistency
        actual_id = entity.identity.id
        if actual_id != expected_id:
            logger.error(
                "ID mismatch in %s: filename suggests '%s', but identity.id is '%s'",
                file_path,
                expected_id,
                actual_id,
            )
            raise InvalidDataError(
                f"ID mismatch in {file_path}: filename '{expected_id}' "
                f"does not match identity.id '{actual_id}'",
                file_path,
            )

        entities[actual_id] = entity
        logger.debug("Loaded %s: %s", entity_type, actual_id)

    return entities  # type: ignore[return-value]


def save_simulation(path: Path, simulation: Simulation) -> None:
    """Save complete simulation state to disk.

    Args:
        path: Path to simulation folder.
        simulation: Simulation instance to save.

    Raises:
        StorageIOError: File write failed.

    Note:
        Does not create folder structure. Folder must exist.

    Example:
        >>> save_simulation(Path("simulations/my-sim"), sim)
    """
    # Save characters
    chars_dir = path / "characters"
    if chars_dir.exists():
        for char_id, character in simulation.characters.items():
            char_file = chars_dir / f"{char_id}.json"
            _save_entity(char_file, character)

    # Save locations
    locs_dir = path / "locations"
    if locs_dir.exists():
        for loc_id, location in simulation.locations.items():
            loc_file = locs_dir / f"{loc_id}.json"
            _save_entity(loc_file, location)

    # Save simulation.json (metadata only, without characters/locations)
    sim_file = path / "simulation.json"
    sim_data = {
        "id": simulation.id,
        "current_tick": simulation.current_tick,
        "created_at": simulation.created_at.isoformat(),
        "status": simulation.status,
    }

    try:
        with open(sim_file, "w", encoding="utf-8") as f:
            json.dump(sim_data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Cannot write %s: %s", sim_file, e)
        raise StorageIOError(f"Cannot write {sim_file}: {e}", sim_file, e)

    logger.debug(
        "Saved simulation %s: tick=%d, %d characters, %d locations",
        simulation.id,
        simulation.current_tick,
        len(simulation.characters),
        len(simulation.locations),
    )


def _save_entity(file_path: Path, entity: Character | Location) -> None:
    """Save a single entity to a JSON file.

    Args:
        file_path: Path to output file.
        entity: Entity to save.

    Raises:
        StorageIOError: File write failed.
    """
    try:
        data = entity.model_dump(mode="json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Cannot write %s: %s", file_path, e)
        raise StorageIOError(f"Cannot write {file_path}: {e}", file_path, e)


def reset_simulation(sim_id: str, base_path: Path) -> None:
    """Reset simulation to template state.

    Copies template over working simulation, clearing logs.
    Creates working simulation folder if it doesn't exist.

    Args:
        sim_id: Simulation identifier.
        base_path: Base path containing simulations/ folder.

    Raises:
        TemplateNotFoundError: Template doesn't exist.
        StorageIOError: Copy operation failed.

    Example:
        >>> reset_simulation("demo-sim", Path("/project"))
    """
    template_path = base_path / "simulations" / "_templates" / sim_id
    target_path = base_path / "simulations" / sim_id

    # Check template exists
    if not template_path.exists() or not template_path.is_dir():
        logger.error("Template not found: %s", template_path)
        raise TemplateNotFoundError(sim_id, template_path)

    try:
        # Remove existing target if present
        if target_path.exists():
            shutil.rmtree(target_path)
            logger.debug("Removed existing simulation: %s", target_path)

        # Copy template to target
        shutil.copytree(template_path, target_path)
        logger.debug("Copied template to: %s", target_path)

        # Ensure logs folder exists and is empty
        logs_path = target_path / "logs"
        if logs_path.exists():
            # Clear logs folder contents (keep the folder)
            for item in logs_path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            logger.debug("Cleared logs folder: %s", logs_path)
        else:
            logs_path.mkdir()
            logger.debug("Created logs folder: %s", logs_path)

        logger.info("Reset simulation '%s' to template state", sim_id)

    except OSError as e:
        logger.error("Failed to reset simulation '%s': %s", sim_id, e)
        raise StorageIOError(f"Failed to reset simulation '{sim_id}': {e}", target_path, e)
