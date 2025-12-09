# TS-REFACTOR-PRINT: Рефакторинг вывода — убрать print(), привести спеки в соответствие

## References

- `docs/Thing' Sandbox Architecture.md` — секция 11 "Формат логирования"
- `docs/specs/util_logging_config.md` — спецификация логгера
- `src/cli.py` — референс использования `typer.echo()` для CLI output
- Все спеки в `docs/specs/`

## Context

В проекте два механизма вывода:

| Контекст | Инструмент | Когда использовать |
|----------|------------|-------------------|
| CLI user-facing output | `typer.echo()` | Сообщения для пользователя в командах CLI |
| Internal modules | `logging` | Всё остальное: debug, info, warning, error |

**Проблема:** в коде могут остаться `print()`, а в спеках есть устаревшие примеры с `print(..., file=sys.stderr)`.

**Референс CLI (src/cli.py):**
```python
# Ошибки — в stderr
typer.echo(f"Configuration error: {e}", err=True)
typer.echo(f"Simulation '{sim_id}' not found", err=True)

# Успешный вывод — в stdout
typer.echo(f"[{sim_id}] Reset to template.")
typer.echo(f"{sim_id}: tick {simulation.current_tick}, ...")
```

**Референс логгера (Architecture секция 11):**
```python
logger = logging.getLogger(__name__)
logger.info("Loaded config")
logger.warning("Fallback to idle")
logger.error("Phase failed")  # перед raise
```

## Steps

### 1. Аудит кода на print()

Найти все `print(` в коде:
```bash
grep -rn "print(" src/ --include="*.py"
```

Для каждого найденного:
- Если в CLI команде → заменить на `typer.echo()`
- Если в другом модуле → заменить на `logger.xxx()`
- Если это debug/temp код → удалить

### 2. Аудит спек на print()

Найти все `print(` в спеках:
```bash
grep -rn "print(" docs/specs/ --include="*.md"
```

Известные проблемные места (примеры с `print(..., file=sys.stderr)`):
- `docs/specs/util_exit_codes.md`
- `docs/specs/util_storage.md`
- `docs/specs/util_prompts.md`
- `docs/specs/core_runner.md`

Для каждого:
- Если это пример CLI кода → заменить на `typer.echo(..., err=True)`
- Если это пример внутреннего модуля → заменить на `logger.error()`

**Важно:** примеры типа `print(response.parsed.answer)` в Usage Examples — это демонстрация API, НЕ вывод в консоль. Их НЕ трогать.

### 3. Проверка соответствия спек коду

После рефакторинга убедиться, что примеры в спеках соответствуют реальному коду:
- `core_cli.md` — сверить с `src/cli.py`
- Другие спеки — сверить паттерны error handling

## Testing

```bash
# Активировать venv
source venv/bin/activate

# Проверка качества
ruff check src/ tests/
ruff format src/ tests/
mypy src/

# Тесты
pytest tests/ -v
```

## Deliverables

1. Код без `print()` (кроме возможных `__main__` блоков для отладки)
2. Спеки с актуальными примерами:
   - CLI примеры используют `typer.echo()`
   - Внутренние модули используют `logger`
3. Все тесты проходят
4. Отчёт `TS-REFACTOR-PRINT_REPORT.md`
