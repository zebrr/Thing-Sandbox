# TS-REFACTOR-CONFIG-001: Use TELEGRAM_TEST_CHAT_ID as fallback for chat_id

## References

- Config spec: `docs/specs/core_config.md`
- Current implementation: `src/config.py`

## Context

Проблема: `chat_id` для Telegram хранится в config.toml или simulation.json — оба коммитятся в репо. Нужен способ указать дефолтный chat_id через .env (секрет, не коммитится).

Решение: использовать существующий `TELEGRAM_TEST_CHAT_ID` из .env как fallback. Если после merge config.toml + simulation.json `chat_id` пустой — использовать значение из .env.

## Steps

### 1. Обновить EnvSettings в src/config.py

Добавить поле:
```python
class EnvSettings(BaseSettings):
    openai_api_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_test_chat_id: str | None = None  # NEW
```

### 2. Обновить Config.__init__

Добавить параметр и атрибут:
```python
def __init__(
    self,
    ...
    telegram_test_chat_id: str | None,  # NEW
    project_root: Path,
) -> None:
    ...
    self.telegram_test_chat_id = telegram_test_chat_id  # NEW
```

### 3. Обновить Config.load()

Передать значение из env_settings:
```python
return cls(
    ...
    telegram_test_chat_id=env_settings.telegram_test_chat_id,  # NEW
    project_root=project_root,
)
```

### 4. Обновить resolve_output()

После merge, перед return — добавить fallback логику:
```python
# Fallback: if chat_id empty after merge, use TELEGRAM_TEST_CHAT_ID from .env
if not telegram_data.get("chat_id") and self.telegram_test_chat_id:
    telegram_data["chat_id"] = self.telegram_test_chat_id

return OutputConfig(...)
```

### 5. Обновить комментарий в config.toml

Изменить комментарий к `chat_id`:
```toml
# chat_id: ID чата/канала. Лучше указывать в .env (TELEGRAM_TEST_CHAT_ID) или в simulation.json
chat_id = ""
```

### 6. Обновить docs/specs/core_config.md

- Добавить `telegram_test_chat_id` в описание Config атрибутов
- Обновить описание `resolve_output()` — добавить информацию о fallback логике

## Testing

```bash
# Активировать venv
source .venv/bin/activate

# Проверка качества кода
ruff check src/config.py
ruff format src/config.py
mypy src/config.py

# Запуск тестов config
pytest tests/unit/test_config.py -v

# Проверить что ничего не сломали
pytest tests/unit/ -v
```

**Новые тесты добавить в test_config.py:**

- `test_resolve_output_fallback_chat_id` — если chat_id пустой после merge, берётся telegram_test_chat_id из config
- `test_resolve_output_no_fallback_when_chat_id_set` — если chat_id указан в simulation.json, fallback не применяется
- `test_resolve_output_no_fallback_when_default_empty` — если и chat_id и telegram_test_chat_id пустые, остаётся пустым

## Deliverables

- [ ] `src/config.py` — обновлён с telegram_test_chat_id и fallback логикой
- [ ] `config.toml` — обновлён комментарий к chat_id
- [ ] `docs/specs/core_config.md` — обновлена документация
- [ ] `tests/unit/test_config.py` — добавлены 3 теста
- [ ] Все проверки качества пройдены (ruff, mypy)
- [ ] Все unit тесты проходят
- [ ] Отчёт: `docs/tasks/TS-REFACTOR-CONFIG-001_REPORT.md`
