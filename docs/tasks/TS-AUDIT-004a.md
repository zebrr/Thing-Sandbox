# TS-AUDIT-004a: Logging and Config Refactoring

## References
- `docs/Thing' Sandbox Architecture.md` — секция 11 "Формат логирования"
- `docs/tasks/TS-AUDIT-004_REPORT.md` — findings to fix
- `src/config.py` — config module
- `src/phases/phase1.py`, `src/phases/phase3.py` — print/logging duplication

## Context
AUDIT-004 выявил несколько inconsistencies, которые нужно исправить:
1. Дублирование print() + logging в фазах
2. Приватный `_project_root` используется снаружи
3. Нет единого формата логирования

## Steps

### Part A: Remove duplicate print() calls

В `phase1.py` и `phase3.py` есть паттерн:
```python
logger.warning("Phase 1: %s fallback...", char_id)
print(f"⚠️  Phase 1: {char_id} fallback...")  # ← DELETE
```

**Действие:** удалить все `print()` вызовы для warnings/errors, оставить только `logger.*`.

**Файлы:**
- `src/phases/phase1.py` — удалить print() на строках с fallback messages
- `src/phases/phase3.py` — удалить print() на строках с warning messages

### Part B: Rename `_project_root` → `project_root`

**Файл `src/config.py`:**
- Переименовать атрибут `_project_root` → `project_root`
- Обновить все внутренние использования

**Файлы, использующие `config._project_root`:**
- `src/cli.py`
- `src/runner.py`  
- `src/phases/phase1.py`

Заменить `config._project_root` → `config.project_root`

### Part C: Implement unified logging format

Создать logging configuration согласно Architecture секции 11.

**Формат:**
```
YYYY.MM.DD HH:MM:SS | LEVEL   | 🏷️ module: message
```

**Эмодзи маппинг:**

| Module name (from `__name__`) | Emoji |
|-------------------------------|-------|
| `src.config` | ⚙️ |
| `src.runner` | 🎬 |
| `src.phases.phase1` | 🎭 |
| `src.phases.phase2a` | ⚖️ |
| `src.phases.phase2b` | 📖 |
| `src.phases.phase3` | 🔧 |
| `src.phases.phase4` | 🧠 |
| `src.utils.llm` | 🤖 |
| `src.utils.llm_adapters.*` | 🤖 |
| `src.utils.storage` | 💾 |
| `src.utils.prompts` | 📝 |
| `src.narrators` | 📢 |

**Implementation approach:**

1. Создать `src/utils/logging_config.py`:
   - Custom Formatter class с эмодзи маппингом
   - Функция `setup_logging(level: int = logging.INFO)` для настройки root logger
   - Извлекать короткое имя модуля из `__name__` (e.g., `src.phases.phase1` → `phase1`)

2. Вызывать `setup_logging()` в `cli.py` перед началом работы

**Formatter должен:**
- Форматировать timestamp как `YYYY.MM.DD HH:MM:SS`
- Паддить LEVEL до 7 символов
- Добавлять эмодзи по module name
- Извлекать короткое имя модуля

**Пример реализации:**
```python
class EmojiFormatter(logging.Formatter):
    EMOJI_MAP = {
        "config": "⚙️",
        "runner": "🎬",
        "phase1": "🎭",
        # ... etc
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # Extract short module name from record.name
        # e.g., "src.phases.phase1" → "phase1"
        module = record.name.rsplit(".", 1)[-1]
        emoji = self.EMOJI_MAP.get(module, "📋")
        
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y.%m.%d %H:%M:%S")
        level = record.levelname.ljust(7)
        
        return f"{timestamp} | {level} | {emoji} {module}: {record.getMessage()}"
```

### Part D: Update existing log messages

Review and update log messages in all modules to follow the standard:
- No trailing period
- Include relevant context (entity id, file path, metrics)
- Use appropriate log level

## Testing

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
python -m pytest tests/unit/ -v
```

**Manual verification:**
```bash
# Run with logging visible
python -m src.cli tick demo-sim --verbose
```

Should see formatted output like:
```
2025.06.05 14:32:07 | INFO    | ⚙️ config: Loaded from config.toml
2025.06.05 14:32:07 | INFO    | 🎬 runner: Starting tick 1 for demo-sim
```

## Deliverables

- `src/utils/logging_config.py` — new file with formatter and setup
- `src/config.py` — renamed `project_root`
- `src/cli.py` — call `setup_logging()`, updated `project_root` usage
- `src/runner.py` — updated `project_root` usage
- `src/phases/phase1.py` — removed print(), updated `project_root` usage
- `src/phases/phase3.py` — removed print()
- `tests/unit/test_logging_config.py` — tests for new module
- `docs/specs/util_logging_config.md` — spec for new module
- `docs/tasks/TS-AUDIT-004a_REPORT.md`
