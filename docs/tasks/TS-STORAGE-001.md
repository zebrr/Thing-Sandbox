# TS-STORAGE-001: Реализовать модуль Storage

## References

- Спецификация: `docs/specs/util_storage.md`
- Архитектура: `docs/Thing' Sandbox Architecture.md` (секции 3, 8)
- JSON-схемы: `src/schemas/Character.schema.json`, `src/schemas/Location.schema.json`
- Exit codes: `src/utils/exit_codes.py`, `docs/specs/util_exit_codes.md`

## Context

Этапы A.1, A.2, A.3 завершены — структура проекта создана, exit codes и config реализованы. Теперь нужен модуль Storage для чтения/записи симуляций.

Storage — util-компонент, используемый Runner для загрузки состояния симуляции в начале такта и сохранения в конце. Работает с файловой структурой:

```
simulations/sim-01/
  simulation.json         # метаданные
  characters/
    bob.json
  locations/
    tavern.json
```

### Ключевые решения

1. **Единый объект Simulation** — содержит метаданные + все characters + все locations
2. **Pydantic модели** с `extra="allow"` для Character и Location (соответствуют JSON-схемам)
3. **Eager loading** — при загрузке читаем всё сразу в память
4. **Консистентность ID** — имя файла должно совпадать с `identity.id`
5. **Пустые папки валидны** — симуляция без персонажей/локаций допустима
6. **Последовательная запись** — без temp-файлов, атомарность на уровне такта

## Steps

### 1. Изучить спецификацию и схемы

Прочитай:
- `docs/specs/util_storage.md` — полное описание API
- `src/schemas/Character.schema.json` — структура персонажа
- `src/schemas/Location.schema.json` — структура локации

### 2. Реализовать модуль

Создай `src/utils/storage.py`:

**Исключения:**
```python
class SimulationNotFoundError(Exception):
    """Simulation folder doesn't exist."""
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Simulation not found: {path}")

class InvalidDataError(Exception):
    """JSON parsing or validation failed."""
    def __init__(self, message: str, path: Path | None = None):
        self.path = path
        super().__init__(message)

class StorageIOError(Exception):
    """File read/write failed."""
    def __init__(self, message: str, path: Path, cause: Exception | None = None):
        self.path = path
        self.cause = cause
        super().__init__(message)
```

**Pydantic модели (все с `extra="allow"`):**

Character:
- `CharacterIdentity` — id, name, description, triggers (optional)
- `MemoryCell` — tick, text
- `CharacterMemory` — cells (list), summary
- `CharacterState` — location, internal_state (optional), external_intent (optional)
- `Character` — identity, state, memory

Location:
- `LocationConnection` — location_id, description
- `LocationIdentity` — id, name, description, connections (list)
- `LocationState` — moment
- `Location` — identity, state

Simulation:
- `Simulation` — id, current_tick, created_at, status, characters (dict), locations (dict)
- Для `status` используй `Literal["running", "paused"]`
- `characters` и `locations` — это `dict[str, Character]` и `dict[str, Location]`, в JSON не сохраняются (только метаданные)

**Функции:**

`load_simulation(path: Path) -> Simulation`:
1. Проверить существование папки → SimulationNotFoundError
2. Загрузить `simulation.json` → InvalidDataError при ошибках парсинга/валидации
3. Загрузить все `*.json` из `characters/` (если папка существует)
4. Загрузить все `*.json` из `locations/` (если папка существует)
5. Для каждого файла проверить: имя файла (без .json) == identity.id → InvalidDataError если не совпадает
6. Собрать и вернуть Simulation

`save_simulation(path: Path, simulation: Simulation) -> None`:
1. Записать каждый character в `characters/{id}.json`
2. Записать каждую location в `locations/{id}.json`
3. Записать метаданные в `simulation.json` (id, current_tick, created_at, status)
4. При ошибках записи → StorageIOError

**Важные детали:**
- JSON: `indent=2`, `ensure_ascii=False`, encoding `utf-8`
- Используй `model_dump(mode="json")` для сериализации datetime
- Игнорируй не-.json файлы в папках
- При отсутствии папок characters/ или locations/ — возвращай пустые dict

### 3. Написать тесты

Создай `tests/unit/test_storage.py`:

**Тест-кейсы (используй tmp_path для создания тестовых симуляций):**

Загрузка:
- `test_load_simulation_success` — загрузка валидной симуляции со всеми данными
- `test_load_simulation_not_found` — SimulationNotFoundError если папки нет
- `test_load_simulation_invalid_json` — InvalidDataError при битом JSON
- `test_load_simulation_validation_error` — InvalidDataError при невалидных данных
- `test_load_simulation_id_mismatch` — InvalidDataError если bob.json содержит id: "alice"
- `test_load_simulation_empty_characters` — пустой dict если папка characters/ пуста
- `test_load_simulation_empty_locations` — пустой dict если папка locations/ пуста
- `test_load_simulation_missing_folders` — пустые dict если папок нет вообще
- `test_load_simulation_ignores_non_json` — файлы .txt, .md и т.д. игнорируются
- `test_load_simulation_extra_fields` — extra fields в JSON сохраняются в модели

Сохранение:
- `test_save_simulation_success` — все файлы записываются корректно
- `test_save_simulation_io_error` — StorageIOError при ошибке записи (можно мокнуть)
- `test_save_simulation_preserves_extra_fields` — extra fields не теряются при roundtrip

Roundtrip:
- `test_roundtrip` — load → modify → save → load, данные совпадают

**Вспомогательные функции для тестов:**

Создай фикстуру или helper для генерации тестовой симуляции:
```python
def create_test_simulation(tmp_path: Path) -> Path:
    """Creates a valid test simulation structure."""
    sim_path = tmp_path / "test-sim"
    sim_path.mkdir()
    (sim_path / "characters").mkdir()
    (sim_path / "locations").mkdir()
    
    # simulation.json
    (sim_path / "simulation.json").write_text(json.dumps({
        "id": "test-sim",
        "current_tick": 0,
        "created_at": "2025-01-15T10:00:00Z",
        "status": "paused"
    }))
    
    # character
    (sim_path / "characters" / "bob.json").write_text(json.dumps({
        "identity": {"id": "bob", "name": "Bob", "description": "A test character"},
        "state": {"location": "tavern"},
        "memory": {"cells": [], "summary": ""}
    }))
    
    # location
    (sim_path / "locations" / "tavern.json").write_text(json.dumps({
        "identity": {"id": "tavern", "name": "Tavern", "description": "A cozy place", "connections": []},
        "state": {"moment": "Evening"}
    }))
    
    return sim_path
```

### 4. Обновить спецификацию

В `docs/specs/util_storage.md` измени статус:
```
## Status: READY
```

## Testing

```bash
# Активировать venv
source venv/bin/activate

# Проверка качества кода
ruff check src/utils/storage.py
ruff format src/utils/storage.py
mypy src/utils/storage.py

# Запуск тестов
pytest tests/unit/test_storage.py -v

# Проверка импорта
python -c "
from src.utils.storage import (
    load_simulation, save_simulation,
    Simulation, Character, Location,
    SimulationNotFoundError, InvalidDataError, StorageIOError
)
print('Import OK')
"
```

**Ожидаемый результат:**
- ruff: no issues
- mypy: no errors
- pytest: all tests passed (13+ тестов)
- import: prints "Import OK"

## Deliverables

- [ ] `src/utils/storage.py` — реализация модуля
- [ ] `tests/unit/test_storage.py` — юнит-тесты (13+ тест-кейсов)
- [ ] `docs/specs/util_storage.md` — статус обновлён на READY
- [ ] `docs/tasks/TS-STORAGE-001_REPORT.md` — отчёт о выполнении
