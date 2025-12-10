# TS-BACKLOG-005-INTEGRATION-001: Integrate TelegramNarrator into CLI

## References

- Workplan: `docs/Thing' Sandbox BACKLOG-005 Workplan.md` (Этап 4)
- CLI spec: `docs/specs/core_cli.md`
- Narrators spec: `docs/specs/core_narrators.md`
- TelegramClient spec: `docs/specs/util_telegram_client.md`
- Config spec: `docs/specs/core_config.md`

## Context

Этапы 1-3 BACKLOG-005 завершены:
- Config поддерживает `resolve_output()` с merge логикой
- TelegramClient реализован (transport layer)
- TelegramNarrator реализован (business logic, lifecycle methods)

Осталось подключить TelegramNarrator в CLI. Runner уже вызывает lifecycle методы для всех narrators — изменения только в CLI.

## Steps

### 1. Изменить src/cli.py

В функции `_run_tick()` после создания ConsoleNarrator добавить условное создание TelegramNarrator:

```
Логика:
1. Проверить output_config.telegram.enabled == True
2. Проверить output_config.telegram.mode != "none"
3. Если оба условия True:
   a. Проверить config.telegram_bot_token
   b. Если токена нет — вывести warning через typer.echo(..., err=True), продолжить без Telegram
   c. Если токен есть — создать TelegramClient и TelegramNarrator, добавить в narrators
```

Формат warning (паттерн из существующего кода):
```python
typer.echo("Telegram enabled but TELEGRAM_BOT_TOKEN not set", err=True)
```

Импорты добавить в начало файла:
```python
from src.narrators import ConsoleNarrator, TelegramNarrator
from src.utils.telegram_client import TelegramClient
```

### 2. Обновить tests/unit/test_cli.py

Добавить 4 теста с моками:

**test_cli_creates_telegram_narrator**
- Mock: Config с telegram_bot_token, output_config с telegram.enabled=True, mode="full"
- Verify: TelegramNarrator создан и добавлен в narrators

**test_cli_warns_no_token**
- Mock: Config без telegram_bot_token, output_config с telegram.enabled=True
- Verify: typer.echo вызван с err=True, TelegramNarrator НЕ создан

**test_cli_telegram_disabled**
- Mock: output_config с telegram.enabled=False
- Verify: TelegramNarrator НЕ создан, warning НЕ выводится

**test_cli_telegram_mode_none**
- Mock: output_config с telegram.enabled=True, mode="none"
- Verify: TelegramNarrator НЕ создан, warning НЕ выводится

Использовать `unittest.mock.patch` для изоляции. Смотреть существующие тесты в файле для паттернов.

### 3. Обновить docs/specs/core_cli.md

В секции "Implementation Notes" → "Async in Typer" обновить пример `_run_tick()` с логикой создания TelegramNarrator.

Добавить в секцию "Dependencies" → "Internal":
- narrators (ConsoleNarrator, TelegramNarrator)
- utils.telegram_client (TelegramClient)

## Testing

```bash
# Активировать venv
source .venv/bin/activate

# Проверка качества кода
ruff check src/cli.py tests/unit/test_cli.py
ruff format src/cli.py tests/unit/test_cli.py
mypy src/cli.py

# Запуск тестов CLI
pytest tests/unit/test_cli.py -v

# Проверить что ничего не сломали
pytest tests/unit/ -v
```

**Ожидаемый результат:** Все тесты проходят, включая 4 новых теста для Telegram интеграции.

## Deliverables

- [ ] `src/cli.py` — обновлён с условным созданием TelegramNarrator
- [ ] `tests/unit/test_cli.py` — добавлены 4 теста
- [ ] `docs/specs/core_cli.md` — обновлена документация
- [ ] Все проверки качества пройдены (ruff, mypy)
- [ ] Все unit тесты проходят
- [ ] Отчёт: `docs/tasks/TS-BACKLOG-005-INTEGRATION-001_REPORT.md`
