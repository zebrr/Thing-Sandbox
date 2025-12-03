# util_storage.md

## Status: READY

Storage module for Thing' Sandbox. Loads and saves simulation state — simulation metadata, 
characters, and locations. Validates data using Pydantic models. Provides atomic save 
operations at tick level.

---

## Public API

### Data Models

#### Simulation

Main container for simulation state. Loaded from disk, modified in memory, saved back.

```python
class Simulation(BaseModel):
    id: str
    current_tick: int = 0
    created_at: datetime
    status: Literal["running", "paused"] = "paused"
    characters: dict[str, Character] = {}
    locations: dict[str, Location] = {}
```

- **id** — simulation identifier, matches folder name
- **current_tick** — last completed tick number (0 = fresh simulation)
- **created_at** — ISO 8601 timestamp
- **status** — "running" during tick execution, "paused" between ticks
- **characters** — all characters keyed by identity.id
- **locations** — all locations keyed by identity.id

#### Character

Character state model. Corresponds to `Character.schema.json`.

```python
class CharacterIdentity(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    description: str
    triggers: str | None = None

class MemoryCell(BaseModel):
    model_config = ConfigDict(extra="allow")
    tick: int
    text: str

class CharacterMemory(BaseModel):
    model_config = ConfigDict(extra="allow")
    cells: list[MemoryCell] = []
    summary: str = ""

class CharacterState(BaseModel):
    model_config = ConfigDict(extra="allow")
    location: str
    internal_state: str | None = None
    external_intent: str | None = None

class Character(BaseModel):
    model_config = ConfigDict(extra="allow")
    identity: CharacterIdentity
    state: CharacterState
    memory: CharacterMemory
```

#### Location

Location state model. Corresponds to `Location.schema.json`.

```python
class LocationConnection(BaseModel):
    model_config = ConfigDict(extra="allow")
    location_id: str
    description: str

class LocationIdentity(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    description: str
    connections: list[LocationConnection] = []

class LocationState(BaseModel):
    model_config = ConfigDict(extra="allow")
    moment: str = ""

class Location(BaseModel):
    model_config = ConfigDict(extra="allow")
    identity: LocationIdentity
    state: LocationState
```

---

### Functions

#### load_simulation(path: Path) -> Simulation

Loads complete simulation state from disk.

- **Input**: 
  - path — path to simulation folder (e.g., `Path("simulations/sim-01")`)
- **Returns**: Simulation instance with all characters and locations loaded
- **Raises**:
  - SimulationNotFoundError — simulation folder doesn't exist
  - InvalidDataError — JSON parsing failed, validation failed, or id mismatch
  - StorageIOError — file read failed
- **Behavior**:
  1. Verify simulation folder exists
  2. Load and parse `simulation.json`
  3. Load all `characters/*.json` files
  4. Load all `locations/*.json` files
  5. Validate id consistency (filename must match identity.id)
  6. Return populated Simulation object

#### save_simulation(path: Path, simulation: Simulation) -> None

Saves complete simulation state to disk.

- **Input**:
  - path — path to simulation folder
  - simulation — Simulation instance to save
- **Returns**: None
- **Raises**:
  - StorageIOError — file write failed
- **Behavior**:
  1. Write each `characters/{id}.json`
  2. Write each `locations/{id}.json`
  3. Write `simulation.json` (without characters/locations, just metadata)
- **Note**: Does not create folder structure. Folder must exist.

#### reset_simulation(sim_id: str, base_path: Path) -> None

Resets simulation to template state.

- **Input**:
  - sim_id — simulation identifier
  - base_path — base path containing simulations/ folder
- **Returns**: None
- **Raises**:
  - TemplateNotFoundError — template doesn't exist
  - StorageIOError — copy operation failed
- **Behavior**:
  1. Check template exists at `{base_path}/simulations/_templates/{sim_id}/`
  2. If not → raise TemplateNotFoundError
  3. Remove existing target simulation if present
  4. Copy template to `{base_path}/simulations/{sim_id}/`
  5. Ensure logs folder exists and is empty
- **Note**: Creates target folder if it doesn't exist.

---

### Exceptions

#### SimulationNotFoundError

Raised when simulation folder doesn't exist.

```python
class SimulationNotFoundError(Exception):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Simulation not found: {path}")
```

#### InvalidDataError

Raised when data validation fails.

```python
class InvalidDataError(Exception):
    def __init__(self, message: str, path: Path | None = None):
        self.path = path
        super().__init__(message)
```

Covers:
- JSON syntax errors
- Pydantic validation failures
- Filename/id mismatch

#### StorageIOError

Raised when file operations fail.

```python
class StorageIOError(Exception):
    def __init__(self, message: str, path: Path, cause: Exception | None = None):
        self.path = path
        self.cause = cause
        super().__init__(message)
```

#### TemplateNotFoundError

Raised when simulation template doesn't exist.

```python
class TemplateNotFoundError(Exception):
    def __init__(self, sim_id: str, template_path: Path):
        self.sim_id = sim_id
        self.template_path = template_path
        super().__init__(f"Template not found for '{sim_id}': {template_path}")
```

---

## Dependencies

- **Standard Library**: pathlib, json, datetime
- **External**: pydantic>=2.0
- **Internal**: None

---

## Error Handling

### Exit Code Mapping (for CLI/Runner)

| Exception | Exit Code |
|-----------|-----------|
| SimulationNotFoundError | EXIT_INPUT_ERROR (2) |
| InvalidDataError | EXIT_INPUT_ERROR (2) |
| StorageIOError | EXIT_IO_ERROR (5) |
| TemplateNotFoundError | EXIT_INPUT_ERROR (2) |

### Validation Rules

- **Filename/ID match**: `characters/bob.json` must contain `identity.id: "bob"`
- **Required fields**: as defined in Pydantic models
- **Extra fields**: allowed (models use `extra="allow"`)

### Edge Cases

- Empty `characters/` folder → empty dict, valid
- Empty `locations/` folder → empty dict, valid
- Missing `characters/` folder → empty dict, valid
- Missing `locations/` folder → empty dict, valid
- Non-JSON files in folders → ignored (only `*.json` loaded)

---

## File Structure

### On Disk

```
simulations/sim-01/
  simulation.json         # metadata only
  characters/
    bob.json
    elvira.json
  locations/
    tavern.json
    forest.json
```

### simulation.json

```json
{
  "id": "sim-01",
  "current_tick": 42,
  "created_at": "2025-01-15T10:00:00Z",
  "status": "paused"
}
```

### characters/bob.json

Full Character as per `Character.schema.json`.

### locations/tavern.json

Full Location as per `Location.schema.json`.

---

## Usage Examples

### Basic Load/Save Cycle

```python
from pathlib import Path
from src.utils.storage import load_simulation, save_simulation

# Load
sim = load_simulation(Path("simulations/my-sim"))

# Modify
sim.current_tick += 1
sim.status = "paused"
sim.characters["bob"].state.location = "forest"

# Save
save_simulation(Path("simulations/my-sim"), sim)
```

### Error Handling

```python
from src.utils.storage import (
    load_simulation, 
    SimulationNotFoundError, 
    InvalidDataError,
    StorageIOError,
)
from src.utils.exit_codes import EXIT_INPUT_ERROR, EXIT_IO_ERROR
import sys

try:
    sim = load_simulation(path)
except SimulationNotFoundError as e:
    print(f"Simulation not found: {e.path}", file=sys.stderr)
    sys.exit(EXIT_INPUT_ERROR)
except InvalidDataError as e:
    print(f"Invalid data: {e}", file=sys.stderr)
    sys.exit(EXIT_INPUT_ERROR)
except StorageIOError as e:
    print(f"IO error: {e}", file=sys.stderr)
    sys.exit(EXIT_IO_ERROR)
```

### Accessing Characters by Location

```python
sim = load_simulation(path)

# Get all characters in tavern
tavern_chars = [
    char for char in sim.characters.values()
    if char.state.location == "tavern"
]
```

---

## Test Coverage

- **test_storage.py**
  - test_load_simulation_success — loads valid simulation
  - test_load_simulation_not_found — raises SimulationNotFoundError
  - test_load_simulation_invalid_json — raises InvalidDataError
  - test_load_simulation_validation_error — raises InvalidDataError
  - test_load_simulation_id_mismatch — raises InvalidDataError
  - test_load_simulation_empty_characters — returns empty dict
  - test_load_simulation_empty_locations — returns empty dict
  - test_load_simulation_missing_folders — returns empty dicts
  - test_load_simulation_ignores_non_json — skips non-.json files
  - test_save_simulation_success — saves all files
  - test_save_simulation_io_error — raises StorageIOError
  - test_save_simulation_preserves_extra_fields — extra fields not lost
  - test_roundtrip — load → modify → save → load matches
  - test_reset_simulation_success — resets simulation to template state
  - test_reset_simulation_creates_target — creates target if doesn't exist
  - test_reset_simulation_clears_logs — clears logs folder contents
  - test_reset_simulation_template_not_found — raises TemplateNotFoundError
  - test_reset_simulation_creates_logs_if_missing — creates logs folder if template lacks one

---

## Implementation Notes

### JSON Serialization

Use Pydantic's built-in serialization:
```python
# Save
data = simulation.model_dump(mode="json")
json.dump(data, f, indent=2, ensure_ascii=False)

# Load
data = json.load(f)
simulation = Simulation.model_validate(data)
```

### DateTime Handling

`created_at` uses ISO 8601 format. Pydantic handles parsing automatically.

### File Encoding

All JSON files use UTF-8 encoding.

### Logging

- DEBUG: files loaded/saved
- WARNING: none expected
- ERROR: before raising exceptions
