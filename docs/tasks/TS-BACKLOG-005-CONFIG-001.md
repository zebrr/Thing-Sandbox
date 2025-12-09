# TS-BACKLOG-005-CONFIG-001: Output Config с Merge Логикой

## References

Прочитать перед началом работы:
- `docs/Thing' Sandbox Architecture.md` - архитектура проекта
- `docs/Thing' Sandbox BACKLOG-005 Workplan.md` — общий план, этап 1
- `docs/specs/core_config.md` — текущая спецификация Config
- `docs/specs/core_cli.md` — текущая спецификация CLI
- `docs/specs/core_runner.md` — текущая спецификация Runner
- `src/config.py` — текущая реализация
- `src/cli.py` — текущая реализация
- `src/runner.py` — текущая реализация

## Context

Готовим инфраструктуру для Telegram Narrator. Нужно:
1. Расширить `TelegramOutputConfig` полями mode, group_intentions, group_narratives
2. Убрать мёртвое поле `console.enabled` (нигде не используется)
3. Добавить метод `Config.resolve_output(simulation)` для merge config.toml defaults + simulation.json overrides
4. Изменить flow в CLI: загружать simulation ДО создания narrators, чтобы `resolve_output()` мог получить overrides

**Ключевое изменение flow:**

Было:
```
CLI: config = Config.load()
CLI: narrators = [ConsoleNarrator()]
CLI: runner = TickRunner(config, narrators)
Runner.run_tick(sim_id): simulation = load_simulation(...)
```

Станет:
```
CLI: config = Config.load()
CLI: simulation = load_simulation(sim_path)
CLI: output_config = config.resolve_output(simulation)
CLI: narrators = [ConsoleNarrator(show_narratives=output_config.console.show_narratives)]
CLI: runner = TickRunner(config, narrators)
Runner.run_tick(simulation): # simulation уже загружена
```

## Steps

### 1. Обновить config.py

**1.1. ConsoleOutputConfig — убрать enabled:**
```python
class ConsoleOutputConfig(BaseModel):
    show_narratives: bool = True
    # enabled убран
```

**1.2. TelegramOutputConfig — добавить поля:**
```python
class TelegramOutputConfig(BaseModel):
    enabled: bool = False
    chat_id: str = ""
    mode: Literal["none", "narratives", "narratives_stats", "full", "full_stats"] = "none"
    group_intentions: bool = True
    group_narratives: bool = True
```

**1.3. Добавить метод resolve_output в класс Config:**
```python
def resolve_output(self, simulation: Simulation | None = None) -> OutputConfig:
    """Merge config.toml defaults with simulation.json overrides.
    
    Args:
        simulation: Loaded simulation with potential output overrides in __pydantic_extra__.
                   If None, returns defaults from config.toml.
    
    Returns:
        OutputConfig with merged values.
    """
    # Start with defaults as dicts
    console_data = self.output.console.model_dump()
    file_data = self.output.file.model_dump()
    telegram_data = self.output.telegram.model_dump()
    
    # Merge overrides from simulation if present
    if simulation is not None:
        extra = simulation.__pydantic_extra__ or {}
        override = extra.get("output", {})
        
        if "console" in override:
            console_data.update(override["console"])
        if "file" in override:
            file_data.update(override["file"])
        if "telegram" in override:
            telegram_data.update(override["telegram"])
    
    return OutputConfig(
        console=ConsoleOutputConfig.model_validate(console_data),
        file=FileOutputConfig.model_validate(file_data),
        telegram=TelegramOutputConfig.model_validate(telegram_data),
    )
```

**1.4. Добавить import:**
```python
from src.utils.storage import Simulation
```

Использовать `TYPE_CHECKING` чтобы избежать circular import:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.storage import Simulation
```

И в сигнатуре:
```python
def resolve_output(self, simulation: "Simulation | None" = None) -> OutputConfig:
```

### 2. Обновить runner.py

**2.1. Изменить сигнатуру run_tick:**

Было:
```python
async def run_tick(self, sim_id: str) -> TickReport:
```

Станет:
```python
async def run_tick(self, simulation: Simulation, sim_path: Path) -> TickReport:
```

**2.2. Убрать load_simulation из run_tick:**

Удалить строки:
```python
# Step 1: Resolve path and load simulation
sim_path = self._config.project_root / "simulations" / sim_id
simulation = load_simulation(sim_path)
```

Начинать сразу с:
```python
sim_id = simulation.id
logger.info(
    "Starting tick %d for %s (%d chars, %d locs)",
    ...
)
```

**2.3. Обновить save_simulation вызов:**

`sim_path` теперь приходит как параметр, не нужно вычислять.

**2.4. Обновить импорты:**

Убрать `load_simulation` из импорта (если больше не используется), добавить `Path`:
```python
from pathlib import Path
```

### 3. Обновить cli.py

**3.1. Команда run — новый flow:**

```python
@app.command()
def run(sim_id: str) -> None:
    """Run simulation tick."""
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
```

**3.2. Обновить _run_tick:**

```python
async def _run_tick(
    config: Config,
    simulation: Simulation,
    sim_path: Path,
    output_config: OutputConfig,
) -> None:
    """Execute tick asynchronously."""
    narrators = [ConsoleNarrator(show_narratives=output_config.console.show_narratives)]
    runner = TickRunner(config, narrators)
    await runner.run_tick(simulation, sim_path)
```

**3.3. Добавить импорты:**

```python
from pathlib import Path
from src.config import Config, ConfigError, OutputConfig
from src.utils.storage import Simulation
```

### 4. Обновить config.toml

```toml
[output.console]
show_narratives = true

[output.file]
enabled = true

[output.telegram]
enabled = false
chat_id = ""
mode = "none"
group_intentions = true
group_narratives = true
```

### 5. Обновить simulation.json (demo-sim и template)

Добавить пример output секции в оба файла:

`simulations/demo-sim/simulation.json`:
```json
{
  "id": "demo-sim",
  "current_tick": 0,
  "created_at": "2025-06-02T12:00:00Z",
  "status": "paused",
  "output": {
    "telegram": {
      "enabled": false,
      "chat_id": "",
      "mode": "none"
    }
  }
}
```

`simulations/_templates/demo-sim/simulation.json`:
```json
{
  "id": "demo-sim",
  "current_tick": 0,
  "created_at": "2025-06-02T12:00:00Z",
  "status": "paused",
  "output": {
    "telegram": {
      "enabled": false,
      "chat_id": "",
      "mode": "none"
    }
  }
}
```

### 6. Обновить спецификации

**6.1. docs/specs/core_config.md:**

- Убрать `enabled` из ConsoleOutputConfig
- Добавить новые поля в TelegramOutputConfig (mode, group_intentions, group_narratives)
- Добавить секцию для `resolve_output()` метода
- Обновить примеры config.toml
- Добавить тесты в Test Coverage

**6.2. docs/specs/core_cli.md:**

- Обновить flow команды run (загрузка simulation перед narrators)
- Обновить сигнатуру _run_tick
- Обновить Dependencies (добавить OutputConfig, Simulation)

**6.3. docs/specs/core_runner.md:**

- Изменить сигнатуру `run_tick(sim_id)` → `run_tick(simulation, sim_path)`
- Убрать step 1 (Load simulation) из Tick Execution Flow
- Обновить примеры использования

## Testing

После реализации:

```bash
cd /path/to/thing-sandbox
source .venv/bin/activate

# Качество кода
ruff check src/config.py src/cli.py src/runner.py
ruff format src/config.py src/cli.py src/runner.py
mypy src/config.py src/cli.py src/runner.py

# Тесты
pytest tests/unit/test_config.py -v
pytest tests/unit/test_cli.py -v
pytest tests/unit/test_runner.py -v

# Полный прогон
pytest
```

### Новые тесты для test_config.py

```python
class TestResolveOutput:
    def test_resolve_output_no_simulation_returns_defaults(self, config):
        """resolve_output(None) returns config.toml defaults."""
        result = config.resolve_output(None)
        assert result.console.show_narratives == True
        assert result.telegram.mode == "none"

    def test_resolve_output_simulation_without_output_returns_defaults(self, config):
        """Simulation without output section returns defaults."""
        simulation = Simulation(
            id="test",
            current_tick=0,
            created_at=datetime.now(),
            status="paused",
        )
        result = config.resolve_output(simulation)
        assert result.telegram.enabled == False

    def test_resolve_output_partial_override(self, config):
        """Partial override merges with defaults."""
        simulation = Simulation(
            id="test",
            current_tick=0,
            created_at=datetime.now(),
            status="paused",
        )
        # Simulate __pydantic_extra__ with partial override
        object.__setattr__(simulation, "__pydantic_extra__", {
            "output": {
                "telegram": {"enabled": True, "chat_id": "123"}
            }
        })
        
        result = config.resolve_output(simulation)
        assert result.telegram.enabled == True
        assert result.telegram.chat_id == "123"
        assert result.telegram.mode == "none"  # default preserved
        assert result.telegram.group_intentions == True  # default preserved

    def test_resolve_output_full_override(self, config):
        """Full override replaces all values."""
        simulation = Simulation(...)
        object.__setattr__(simulation, "__pydantic_extra__", {
            "output": {
                "console": {"show_narratives": False},
                "file": {"enabled": False},
                "telegram": {
                    "enabled": True,
                    "chat_id": "999",
                    "mode": "full_stats",
                    "group_intentions": False,
                    "group_narratives": False,
                }
            }
        })
        
        result = config.resolve_output(simulation)
        assert result.console.show_narratives == False
        assert result.file.enabled == False
        assert result.telegram.mode == "full_stats"

    def test_telegram_mode_validation(self, config):
        """Invalid mode raises ValidationError."""
        simulation = Simulation(...)
        object.__setattr__(simulation, "__pydantic_extra__", {
            "output": {"telegram": {"mode": "invalid"}}
        })
        
        with pytest.raises(ValidationError):
            config.resolve_output(simulation)

```

### Обновить существующие тесты

- `test_runner.py` — обновить вызовы `run_tick()` на новую сигнатуру
- `test_cli.py` — обновить моки для нового flow

## Deliverables

- [ ] `src/config.py` — обновлён (ConsoleOutputConfig, TelegramOutputConfig, resolve_output)
- [ ] `src/cli.py` — обновлён (новый flow загрузки)
- [ ] `src/runner.py` — обновлён (новая сигнатура run_tick)
- [ ] `config.toml` — обновлён
- [ ] `simulations/demo-sim/simulation.json` — обновлён
- [ ] `simulations/_templates/demo-sim/simulation.json` — обновлён
- [ ] `docs/specs/core_config.md` — обновлён
- [ ] `docs/specs/core_cli.md` — обновлён
- [ ] `docs/specs/core_runner.md` — обновлён
- [ ] `tests/unit/test_config.py` — новые тесты для resolve_output
- [ ] `tests/unit/test_cli.py` — обновлены для нового flow
- [ ] `tests/unit/test_runner.py` — обновлены для новой сигнатуры
- [ ] ruff check / ruff format / mypy — без ошибок ДО тестов
- [ ] Все тесты проходят
- [ ] Отчёт: `docs/tasks/TS-BACKLOG-005-CONFIG-001_REPORT.md`
