# TS-EXIT-001: Реализовать модуль Exit Codes

## References

- Спецификация: `docs/specs/util_exit_codes.md`
- Архитектура: `docs/Thing' Sandbox Architecture.md` (секция про utils)

## Context

Этап A.1 завершён — структура проекта создана, зависимости установлены. Теперь нужен базовый модуль exit codes, который будет использоваться CLI и Runner для стандартизированной обработки ошибок.

Модуль простой, без внешних зависимостей — только стандартная библиотека `logging`.

## Steps

### 1. Изучить спецификацию

Прочитай `docs/specs/util_exit_codes.md` — там полное описание API.

### 2. Реализовать модуль

Создай `src/utils/exit_codes.py`:

**Константы (6 штук):**
```python
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_RUNTIME_ERROR = 3
EXIT_API_LIMIT_ERROR = 4
EXIT_IO_ERROR = 5
```

**Словари:**
- `EXIT_CODE_NAMES: dict[int, str]` — маппинг код → имя (например, `1: "CONFIG_ERROR"`)
- `EXIT_CODE_DESCRIPTIONS: dict[int, str]` — маппинг код → описание

**Функции:**
- `get_exit_code_name(code: int) -> str` — возвращает имя или `"UNKNOWN({code})"`
- `get_exit_code_description(code: int) -> str` — возвращает описание или `"Unknown exit code: {code}"`
- `log_exit(logger: logging.Logger, code: int, message: str | None = None) -> None` — логирует exit code (SUCCESS через info, остальные через error)

### 3. Написать тесты

Создай `tests/unit/test_exit_codes.py`:

**Тест-кейсы:**
- Все константы имеют правильные значения (0-5)
- `get_exit_code_name` возвращает корректные имена для известных кодов
- `get_exit_code_name` возвращает `"UNKNOWN(99)"` для неизвестного кода
- `get_exit_code_description` возвращает корректные описания
- `get_exit_code_description` возвращает fallback для неизвестного кода
- `log_exit` с SUCCESS вызывает `logger.info`
- `log_exit` с ошибками вызывает `logger.error`
- `log_exit` корректно форматирует сообщение с/без дополнительного message

### 4. Обновить спецификацию

В `docs/specs/util_exit_codes.md` измени статус:
```
## Status: READY
```

## Testing

```bash
# Активировать venv
source venv/bin/activate  # или . venv/bin/activate

# Проверка качества кода
ruff check src/utils/exit_codes.py
ruff format src/utils/exit_codes.py
mypy src/utils/exit_codes.py

# Запуск тестов
pytest tests/unit/test_exit_codes.py -v

# Проверка импорта
python -c "from src.utils.exit_codes import EXIT_SUCCESS, get_exit_code_name, log_exit; print('OK')"
```

**Ожидаемый результат:**
- ruff: no issues
- mypy: no errors
- pytest: all tests passed
- import: prints "OK"

## Deliverables

- [ ] `src/utils/exit_codes.py` — реализация модуля
- [ ] `tests/unit/test_exit_codes.py` — юнит-тесты
- [ ] `docs/specs/util_exit_codes.md` — статус обновлён на READY
- [ ] `docs/tasks/TS-EXIT-001_REPORT.md` — отчёт о выполнении
