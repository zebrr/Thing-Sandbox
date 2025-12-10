# TS-TG-TOPICS-001: Add Telegram Forum Topics Support

## References
- `docs/Thing' Sandbox Architecture.md` - общая архитектура проекта и компонент
- `docs/specs/core_config.md` — спецификация конфигурации
- `docs/specs/core_narrators.md` — спецификация нарраторов
- `docs/specs/util_telegram_client.md` — спецификация Telegram клиента
- `docs/Thing' Sandbox Telegram API Reference.md` — референс Telegram API

## Context
Telegram поддерживает "топики" (темы) в супергруппах с включённым режимом форума. Для отправки сообщения в конкретный топик используется параметр `message_thread_id` в методе `sendMessage`.

Нужно добавить опциональную поддержку `message_thread_id` на всех уровнях конфигурации с сохранением обратной совместимости. Если параметр не указан — поведение не меняется.

**Цепочка конфигурации:**
```
.env (TELEGRAM_TEST_THREAD_ID) → config.toml → simulation.json → resolve_output()
```

**Логика merge:**
- simulation.json перезаписывает только указанные поля config.toml
- Fallback из .env срабатывает если после merge значение = None

## Steps

### 1. Обновить `src/config.py`

**EnvSettings** — добавить поле:
```python
telegram_test_thread_id: int | None = None
```

**TelegramOutputConfig** — добавить поле:
```python
message_thread_id: int | None = None
```

**Config.__init__** — добавить параметр `telegram_test_thread_id: int | None` и сохранить в `self.telegram_test_thread_id`

**Config.load()** — передать `telegram_test_thread_id=env_settings.telegram_test_thread_id`

**resolve_output()** — добавить fallback после существующего для chat_id:
```python
if telegram_data.get("message_thread_id") is None and self.telegram_test_thread_id:
    telegram_data["message_thread_id"] = self.telegram_test_thread_id
```

### 2. Обновить `src/narrators.py`

**TelegramNarrator.__init__** — добавить параметр:
```python
message_thread_id: int | None = None,
```
Сохранить в `self._message_thread_id`

**Все методы _send_*** — передавать `message_thread_id=self._message_thread_id` в вызовы `self._client.send_message()`

### 3. Обновить `src/utils/telegram_client.py`

**send_message()** — добавить параметр:
```python
message_thread_id: int | None = None,
```
Передавать в `_send_single_message()`

**_send_single_message()** — добавить параметр и включить в payload:
```python
if message_thread_id is not None:
    payload["message_thread_id"] = message_thread_id
```

### 4. Обновить `src/runner.py` (если нужно)

Проверить, как создаётся TelegramNarrator — добавить передачу `message_thread_id` из resolved output config.

### 5. Обновить тесты

**tests/unit/test_config.py** — добавить тесты:
- `TestTelegramOutputConfig.test_message_thread_id_default` — None по умолчанию
- `TestTelegramOutputConfig.test_message_thread_id_custom` — принимает int
- `TestEnvLoading.test_env_loading_with_thread_id` — загрузка из .env
- `TestOutputConfig.test_output_config_from_toml_with_thread_id` — загрузка из TOML
- `TestResolveOutput.test_resolve_output_fallback_thread_id` — fallback из .env
- `TestResolveOutput.test_resolve_output_no_fallback_when_thread_id_set` — не перезаписывается
- `TestResolveOutput.test_resolve_output_partial_override_thread_id` — merge работает

**tests/unit/test_telegram_client.py** — добавить тест:
- `test_send_message_with_thread_id` — проверить что message_thread_id попадает в payload

**tests/unit/test_narrators.py** — проверить/добавить тест на прокидывание thread_id в клиент

### 6. Обновить конфиги

**config.toml** — добавить в секцию `[output.telegram]`:
```toml
# message_thread_id: ID топика в супергруппе с форумом (опционально)
# message_thread_id = 123
```

**simulations/demo-sim/simulation.json** — опционально добавить пример (закомментированный или с реальным значением)

### 7. Обновить спецификации

**docs/specs/core_config.md** — добавить:
- `TelegramOutputConfig.message_thread_id` в описание модели
- `TELEGRAM_TEST_THREAD_ID` в описание EnvSettings
- Обновить описание `resolve_output()`

**docs/specs/core_narrators.md** — добавить `message_thread_id` в параметры `TelegramNarrator.__init__`

**docs/specs/util_telegram_client.md** — добавить `message_thread_id` в сигнатуру `send_message()`

## Testing

```bash
cd /Users/askold.romanov/code/Thing-Sandbox
source .venv/bin/activate

# Quality checks
ruff check src/ tests/
ruff format src/ tests/
mypy src/

# Run tests
pytest tests/unit/test_config.py -v
pytest tests/unit/test_telegram_client.py -v
pytest tests/unit/test_narrators.py -v

# Full test suite
pytest
```

**Ожидаемый результат:** все тесты проходят, новые тесты покрывают message_thread_id на всех уровнях.

## Deliverables
- [ ] `src/config.py` — обновлён
- [ ] `src/narrators.py` — обновлён
- [ ] `src/utils/telegram_client.py` — обновлён
- [ ] `src/runner.py` — обновлён (если требуется)
- [ ] `tests/unit/test_config.py` — новые тесты
- [ ] `tests/unit/test_telegram_client.py` — новые тесты
- [ ] `tests/unit/test_narrators.py` — обновлены тесты
- [ ] `config.toml` — добавлен комментарий
- [ ] `docs/specs/core_config.md` — обновлена
- [ ] `docs/specs/core_narrators.md` — обновлена
- [ ] `docs/specs/util_telegram_client.md` — обновлена
- [ ] Отчёт `TS-TG-TOPICS-001_REPORT.md`
