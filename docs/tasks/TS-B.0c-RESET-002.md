# TS-B.0c-RESET-002: Simulation Reset from Template

## References

- `docs/specs/util_storage.md` — storage module specification
- `docs/specs/core_cli.md` — CLI specification  
- `docs/Thing' Sandbox Architecture.md` — project architecture
- `src/utils/storage.py` — current implementation
- `src/cli.py` — current implementation

## Context

При тестировании и демонстрациях симуляция мутирует (tick++, память накапливается). 
Нужен механизм сброса симуляции к начальному состоянию из шаблона.

**Цель:** добавить команду `reset` и инфраструктуру шаблонов.

## Концепция

```
simulations/
  _templates/           # шаблоны (папка с _ не считается симуляцией)
    demo-sim/           # шаблон демо-симуляции
      simulation.json
      characters/
      locations/
      logs/             # пустая папка
  demo-sim/             # рабочая копия (мутирует)
```

**Поведение reset:**
- Есть шаблон → копируем поверх рабочей симуляции (создаём если нет)
- Нет шаблона → `TemplateNotFoundError`
- Папка `logs/` в рабочей симуляции очищается (удаляем содержимое)

## Steps

### 1. Создать папку шаблонов

Скопировать текущую `simulations/demo-sim/` в `simulations/_templates/demo-sim/`.
Убедиться что `logs/` пустая.

### 2. Обновить storage.py

**Добавить исключение:**
```python
class TemplateNotFoundError(Exception):
    """Template for simulation doesn't exist."""
    
    def __init__(self, sim_id: str, template_path: Path) -> None:
        self.sim_id = sim_id
        self.template_path = template_path
        super().__init__(f"Template not found for '{sim_id}': {template_path}")
```

**Добавить функцию:**
```python
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
    """
```

**Алгоритм:**
1. Проверить существование `{base_path}/simulations/_templates/{sim_id}/`
2. Если нет → raise `TemplateNotFoundError`
3. Определить target: `{base_path}/simulations/{sim_id}/`
4. Если target существует → удалить содержимое (или всю папку)
5. Скопировать шаблон в target (shutil.copytree)
6. Очистить `{target}/logs/` (на случай если в шаблоне что-то было)

### 3. Обновить cli.py

**Добавить команду:**
```python
@app.command()
def reset(sim_id: str) -> None:
    """Reset simulation to template state.
    
    Copies template over working simulation, clearing logs.
    Creates simulation folder if it doesn't exist.
    
    Args:
        sim_id: Simulation identifier.
    """
```

**Поведение:**
- Успех → `[{sim_id}] Reset to template.`
- TemplateNotFoundError → `Error: Template for '{sim_id}' not found`, exit 2
- StorageIOError → `Storage error: {e}`, exit 5

### 4. Обновить спецификации

**util_storage.md:**
- Добавить `TemplateNotFoundError` в секцию Exceptions
- Добавить `reset_simulation()` в секцию Functions
- Добавить тесты в Test Coverage

**core_cli.md:**
- Добавить команду `reset` в секцию Commands
- Добавить `TemplateNotFoundError` в Exception Mapping

### 5. Обновить Architecture.md

Добавить новую секцию после "5. Инициализация симуляции":

```markdown
## 5.1 Шаблоны и сброс симуляции

### Папка шаблонов

Шаблоны хранятся в `simulations/_templates/`. Префикс `_` исключает 
папку из списка активных симуляций.

### Сброс к шаблону

Команда `reset` копирует шаблон поверх рабочей симуляции:

\`\`\`bash
python -m src.cli reset demo-sim
\`\`\`

**Поведение:**
- Шаблон существует → копируется поверх рабочей симуляции
- Рабочей симуляции нет → создаётся из шаблона  
- Папка `logs/` очищается
- Шаблона нет → ошибка

### Демо-симуляция

`demo-sim` — тестовая симуляция по мотивам "Войны миров" Уэллса.
Шаблон: `simulations/_templates/demo-sim/`.
```

## Testing

После выполнения:

```bash
# Активировать venv
source venv/bin/activate  # или . venv/bin/activate

# Проверка качества кода
ruff check src/utils/storage.py src/cli.py
ruff format src/utils/storage.py src/cli.py
mypy src/utils/storage.py src/cli.py

# Запустить тесты
pytest tests/ -v

# Ручная проверка
python -m src.cli status demo-sim          # текущий статус
python -m src.cli run demo-sim             # запустить тик (tick станет 1)
python -m src.cli status demo-sim          # tick = 1
python -m src.cli reset demo-sim           # сбросить
python -m src.cli status demo-sim          # tick = 0

# Проверка ошибки — нет шаблона
python -m src.cli reset nonexistent-sim    # должна быть ошибка
```

**Unit тесты для storage.py:**
- `test_reset_simulation_success` — сброс работает
- `test_reset_simulation_creates_target` — создаёт если не было
- `test_reset_simulation_clears_logs` — logs очищается
- `test_reset_simulation_template_not_found` — TemplateNotFoundError

**Unit тесты для cli.py:**
- `test_reset_command_success` — exit 0, правильный вывод
- `test_reset_command_template_not_found` — exit 2

## Deliverables

1. `simulations/_templates/demo-sim/` — папка шаблона
2. `src/utils/storage.py` — добавлены `TemplateNotFoundError`, `reset_simulation()`
3. `src/cli.py` — добавлена команда `reset`
4. `docs/specs/util_storage.md` — обновлена
5. `docs/specs/core_cli.md` — обновлена
6. `docs/Thing' Sandbox Architecture.md` — обновлена
7. `tests/unit/test_storage.py` — тесты reset
8. `tests/unit/test_cli.py` — тесты reset command
9. `docs/tasks/TS-B.0c-RESET-002_REPORT.md` — отчёт
