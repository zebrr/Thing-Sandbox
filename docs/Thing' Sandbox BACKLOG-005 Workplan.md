# Thing' Sandbox: BACKLOG-005 Telegram Narrator Workplan

## Обзор

Реализация вывода симуляции в Telegram-канал. Бот единый (токен в `.env`), но каналы и режимы работы уникальны для каждой симуляции (настройки в `simulation.json`, defaults в `config.toml`).

**Режимы работы:**
- `none` — телеграм отключен для данной симуляции
- `narratives` — только нарративы
- `narratives_stats` — нарративы + статистика
- `full` — намерения + нарративы
- `full_stats` — намерения + нарративы + статистика

**Порядок вывода (mode=full/full_stats):**
1. Intentions (одно или N сообщений)
2. Narratives (одно или M сообщений)

---

## Этап 1: Конфигурация output с merge логикой

Рефакторинг конфигурации вывода: убираем лишнее из `console`, расширяем `telegram`, добавляем merge simulation.json → config.toml.

**STATUS: ЗАВЕРШЁН**

### References

- Архитектура: `docs/Thing' Sandbox Architecture.md`
- Спецификация Config: `docs/specs/core_config.md`
- Спецификация Storage: `docs/specs/util_storage.md`
- Telegram API Reference: `docs/Thing' Sandbox Telegram API Reference.md`

### Изменения в config.toml

**Было:**
```toml
[output.console]
enabled = true
show_narratives = true

[output.file]
enabled = true

[output.telegram]
enabled = false
chat_id = ""
```

**Станет:**
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

**Примечание:** `console.enabled` убираем — runner всегда пишет базовые статусы в консоль, `show_narratives` управляет только выводом нарративов через `ConsoleNarrator`.

### Изменения в config.py

**ConsoleOutputConfig:**
```python
class ConsoleOutputConfig(BaseModel):
    show_narratives: bool = True
    # enabled убран
```

**TelegramOutputConfig:**
```python
class TelegramOutputConfig(BaseModel):
    enabled: bool = False
    chat_id: str = ""
    mode: Literal["none", "narratives", "narratives_stats", "full", "full_stats"] = "none"
    group_intentions: bool = True
    group_narratives: bool = True
```

**Config — новый метод:**
```python
def resolve_output(self, simulation: Simulation | None = None) -> OutputConfig:
    """Merge config.toml defaults with simulation.json overrides.
    
    Args:
        simulation: Loaded simulation with potential output overrides.
                   If None, returns defaults from config.toml.
    
    Returns:
        OutputConfig with merged values.
    """
```

**Логика merge:**
1. Берём defaults из `self.output` (загружены из config.toml)
2. Если `simulation` указан — берём overrides из `simulation.__pydantic_extra__.get("output", {})`
3. Deep merge (2 уровня) поверх defaults
4. Валидируем результат через `OutputConfig.model_validate()`

**Примечание:** Simulation уже загружена в CLI, не нужно читать JSON повторно.

### Изменения в CLI и Runner

**Новый flow:**
```
CLI: config = Config.load()
CLI: simulation = load_simulation(sim_path)
CLI: output_config = config.resolve_output(simulation)
CLI: narrators = [ConsoleNarrator(show_narratives=output_config.console.show_narratives)]
CLI: runner = TickRunner(config, narrators)
Runner.run_tick(simulation, sim_path)  # simulation уже загружена
```

**Изменения в runner.py:**
- Сигнатура: `run_tick(sim_id: str)` → `run_tick(simulation: Simulation, sim_path: Path)`
- Убрать `load_simulation()` из `run_tick` — simulation приходит как параметр

**Изменения в cli.py:**
- Загрузка simulation ДО создания narrators
- Вызов `config.resolve_output(simulation)`
- Передача simulation и sim_path в `runner.run_tick()`

### Формат simulation.json (output секция)

```json
{
  "id": "demo-sim",
  "current_tick": 0,
  "created_at": "2025-06-02T12:00:00Z",
  "status": "paused",
  "output": {
    "console": {
      "show_narratives": false
    },
    "file": {
      "enabled": false
    },
    "telegram": {
      "enabled": true,
      "chat_id": "123456789",
      "mode": "full_stats",
      "group_intentions": true,
      "group_narratives": false
    }
  }
}
```

**Примечание:** `Simulation` модель имеет `extra="allow"`, поэтому `output` секция автоматически сохраняется в `__pydantic_extra__`. Отдельная Pydantic-схема для simulation.json НЕ нужна.

### Тесты

- Валидация `TelegramOutputConfig.mode` (invalid value → error)
- `resolve_output(None)` → defaults
- `resolve_output(simulation)` без output секции → defaults
- `resolve_output(simulation)` с частичным override (только telegram.chat_id)
- `resolve_output(simulation)` с полным override
- Обновить тесты runner.py для новой сигнатуры `run_tick(simulation, sim_path)`
- Обновить тесты cli.py для нового flow

### Артефакты

- Задание: `docs/tasks/TS-BACKLOG-005-CONFIG-001.md`
- Отчёт: `docs/tasks/TS-BACKLOG-005-CONFIG-001_REPORT.md`
- Модули: `src/config.py` (обновить)
- Модули: `src/cli.py` (обновить)
- Модули: `src/runner.py` (обновить)
- Конфиг: `config.toml` (обновить)
- Данные: `simulations/demo-sim/simulation.json` (обновить)
- Данные: `simulations/_templates/demo-sim/simulation.json` (обновить)
- Спецификация: `docs/specs/core_config.md` (обновить)
- Спецификация: `docs/specs/core_cli.md` (обновить)
- Спецификация: `docs/specs/core_runner.md` (обновить)
- Тесты: `tests/unit/test_config.py` (обновить)
- Тесты: `tests/unit/test_cli.py` (обновить)
- Тесты: `tests/unit/test_runner.py` (обновить)

---

## Этап 2: TelegramClient (transport layer)

Async HTTP клиент для Telegram Bot API. Только transport — без бизнес-логики форматирования.

**STATUS: ЗАВЕРШЁН**

### References

- Архитектура: `docs/Thing' Sandbox Architecture.md`
- Telegram API Reference: `docs/Thing' Sandbox Telegram API Reference.md`
- Спецификация Config: `docs/specs/core_config.md` (после Этапа 1)
- Спецификация LLM Adapter (паттерн): `docs/specs/util_llm_adapter_openai.md`

### Задачи

1. Написать спецификацию `docs/specs/util_telegram_client.md`
2. Реализовать `src/utils/telegram_client.py`
3. Написать тесты

### Класс TelegramClient

```python
class TelegramClient:
    def __init__(
        self,
        bot_token: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
    ) -> None:
        """Initialize Telegram client.
        
        Args:
            bot_token: Telegram bot token from BotFather.
            max_retries: Max retry attempts for failed requests.
            retry_delay: Base delay between retries (exponential backoff).
            connect_timeout: Connection timeout in seconds.
            read_timeout: Read timeout in seconds.
        """
    
    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
    ) -> bool:
        """Send text message to chat.
        
        Automatically splits long messages using split_message().
        
        Args:
            chat_id: Numeric chat/channel ID.
            text: Message text (HTML formatted).
            parse_mode: Telegram parse mode.
        
        Returns:
            True if all message parts sent successfully.
        """
    
    async def close(self) -> None:
        """Close HTTP client."""
    
    async def __aenter__(self) -> "TelegramClient":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit — closes HTTP client."""
        await self.close()
```

### Функция split_message

Публичная функция на уровне модуля (не метод класса) для удобства тестирования.

```python
def split_message(
    text: str,
    max_length: int = 3896,
) -> list[str]:
    """Разбивает текст на части для Telegram.
    
    Args:
        text: Исходный текст.
        max_length: Максимальная длина части (с учётом suffix).
    
    Returns:
        Список частей с suffix (M/N) если частей > 1.
    """
```

### Разбивка длинных сообщений

**Лимит:** 4096 символов включая HTML-теги.
**Safe margin:** 200 символов → рабочий лимит 3896.

**Алгоритм:**
1. Если `len(text) <= 3896` → возвращаем `[text]` без suffix
2. Иначе разбиваем по абзацам (`\n\n`)
3. Собираем части, пока не превысим лимит
4. Если один абзац > 3896 → режем по предложениям (`.!?` + пробел)
5. В крайнем случае → режем по словам
6. Добавляем suffix `(1/N)` в конец каждой части

**Пример:**
```
Длинный текст... (1/3)
```

### Error Handling

**Простой подход без кастомных exceptions:**

- Retry с exponential backoff: `delay * (2 ** attempt)`
- Rate limiting (429) → retry с delay из `Retry-After` header (или default 1s)
- 5xx errors → retry
- После `max_retries` неудачных попыток → логируем ERROR, возвращаем `False`
- **Не бросаем исключения** — симуляция не должна падать из-за Telegram
- Все ошибки обрабатываются внутри `try/except Exception`

### Логирование

Используется стандартный `logging` (как в остальном проекте):

```python
logger = logging.getLogger(__name__)
```

- **DEBUG**: каждый отправленный запрос (`chat_id`, длина текста, `part M/N`)
- **WARNING**: retry attempt (`attempt`, `delay`, `status_code`)
- **ERROR**: все попытки исчерпаны (`chat_id`, `last_error`)

### HTTP клиент

Используем `httpx.AsyncClient` (уже есть в зависимостях для OpenAI).

### Тесты

**Unit тесты split_message (без моков):**
- Короткий текст → `[text]` без suffix
- Длинный текст с абзацами → разбивка по абзацам + suffix
- Один очень длинный абзац → разбивка по предложениям
- Одно очень длинное предложение → разбивка по словам
- Suffix `(M/N)` корректный

**Unit тесты TelegramClient с mocked httpx:**
- Успешная отправка
- Retry при 429 (с Retry-After)
- Retry при 5xx
- Все попытки исчерпаны → возвращает False
- Context manager (`async with`)

**Integration тест** (требует бота и канал) — опционально, маркер `@pytest.mark.telegram`

### Артефакты

- Задание: `docs/tasks/TS-BACKLOG-005-CLIENT-001.md`
- Отчёт: `docs/tasks/TS-BACKLOG-005-CLIENT-001_REPORT.md`
- Спецификация: `docs/specs/util_telegram_client.md` (новая)
- Модуль: `src/utils/telegram_client.py` (новый)
- Зависимости: `requirements.txt` (проверить httpx)
- Тесты: `tests/unit/test_telegram_client.py` (новый)

---

## Этап 3: TelegramNarrator (business logic)

Форматирование и отправка tick report в Telegram. Реализует интерфейс `Narrator`.

**STATUS: не начат**

### References

- Архитектура: `docs/Thing' Sandbox Architecture.md`
- Telegram API Reference: `docs/Thing' Sandbox Telegram API Reference.md`
- Спецификация Config: `docs/specs/core_config.md` (после Этапа 1)
- Спецификация TelegramClient: `docs/specs/util_telegram_client.md` (после Этапа 2)
- Спецификация Narrators: `docs/specs/core_narrators.md`
- Спецификация Runner: `docs/specs/core_runner.md`

### Задачи

1. Написать спецификацию `docs/specs/core_telegram_narrator.md`
2. Реализовать `TelegramNarrator` в `src/narrators.py`
3. Написать тесты

### Класс TelegramNarrator

```python
class TelegramNarrator:
    def __init__(
        self,
        client: TelegramClient,
        chat_id: str,
        mode: str,
        group_intentions: bool,
        group_narratives: bool,
    ) -> None:
        """Initialize Telegram narrator.
        
        Args:
            client: TelegramClient instance.
            chat_id: Target chat/channel ID.
            mode: Output mode (narratives, narratives_stats, full, full_stats).
            group_intentions: Group all intentions in one message.
            group_narratives: Group all narratives in one message.
        """
    
    def output(self, report: TickReport) -> None:
        """Output tick report to Telegram.
        
        Runs async send in sync context via asyncio.run().
        
        Args:
            report: TickReport from completed tick.
        """
    
    async def _send_async(self, report: TickReport) -> None:
        """Async implementation of output."""
```

### Форматы сообщений

**Intentions (mode=full/full_stats, group_intentions=true):**
```html
🎯 <b>demo-sim — tick #42 | Intentions</b>

<b>Ogilvy:</b>
Approach the cylinder to examine it more closely...

<b>Henderson:</b>
Interview locals about what they witnessed...

───
📊 <i>4,200 tok · 1,100 reason · 2.1s</i>
```

**Intentions (mode=full/full_stats, group_intentions=false):**
```html
🎯 <b>demo-sim — tick #42 | Intentions: Ogilvy</b>

Approach the cylinder to examine it more closely...

───
📊 <i>2,100 tok · 550 reason · 1.0s</i>
```

**Narratives (group_narratives=true):**
```html
📖 <b>demo-sim — tick #42 | Narratives</b>

<b>Horsell Common</b>
Ogilvy cautiously approaches the pit...

<b>The Red Lion Inn</b>
Henderson scribbles notes furiously...

───
📊 <i>8,250 tok · 2,100 reason · 4.1s</i>
```

**Narratives (group_narratives=false):**
```html
📖 <b>demo-sim — tick #42 | Narratives: Horsell Common</b>

Ogilvy cautiously approaches the pit...

───
📊 <i>4,125 tok · 1,050 reason · 2.0s</i>
```

### Stats Footer

Добавляется к **КАЖДОМУ** сообщению (не только к последнему).

**Формат (режимы _stats):**
```html

───
📊 <i>12,450 tok · 3,200 reason · 6.2s</i>
```

**Примечание:** Stats показывает данные релевантные конкретному сообщению:
- Для grouped intentions — сумма по всем персонажам Phase 1
- Для single intention — данные одного персонажа
- Для grouped narratives — сумма Phase 2a + Phase 2b
- Для single narrative — данные одной локации

### Источники данных

- Intentions: `report.phases["phase1"].data` (dict char_id → IntentionResponse)
- Narratives: `report.narratives` (dict loc_id → narrative text)
- Location names: `report.location_names` (dict loc_id → display name)
- Character names: `report.simulation.characters[char_id].identity.name`
- Stats: `report.phases["phaseX"].stats` (BatchStats) и `report.phases["phaseX"].duration`

### Обработка ошибок

- Ошибки TelegramClient логируются, но не пробрасываются
- Narrator.output() не должен бросать исключения
- При ошибке отправки — warning в лог, продолжаем

### Тесты

- Unit тесты с mocked TelegramClient:
  - Формат intentions (grouped)
  - Формат intentions (per-character)
  - Формат narratives (grouped)
  - Формат narratives (per-location)
  - Stats footer присутствует для _stats режимов
  - Stats footer отсутствует для non-stats режимов
  - mode=narratives → intentions не отправляются

### Артефакты

- Задание: `docs/tasks/TS-BACKLOG-005-NARRATOR-001.md`
- Отчёт: `docs/tasks/TS-BACKLOG-005-NARRATOR-001_REPORT.md`
- Спецификация: `docs/specs/core_telegram_narrator.md` (новая)
- Модуль: `src/narrators.py` (обновить — добавить TelegramNarrator)
- Спецификация: `docs/specs/core_narrators.md` (обновить)
- Тесты: `tests/unit/test_telegram_narrator.py` (новый)
- Тесты: `tests/unit/test_narrators.py` (обновить)

---

## Этап 4: Интеграция в Runner

Подключение TelegramNarrator к TickRunner через CLI.

**STATUS: не начат**

### References

- Архитектура: `docs/Thing' Sandbox Architecture.md`
- Спецификация Config: `docs/specs/core_config.md` (после Этапа 1)
- Спецификация TelegramClient: `docs/specs/util_telegram_client.md` (после Этапа 2)
- Спецификация TelegramNarrator: `docs/specs/core_telegram_narrator.md` (после Этапа 3)
- Спецификация Narrators: `docs/specs/core_narrators.md` (после Этапа 3)
- Спецификация Runner: `docs/specs/core_runner.md`
- Спецификация CLI: `docs/specs/core_cli.md`

### Изменения в cli.py

**Команда run:**
```python
@app.command()
def run(sim_id: str) -> None:
    config = Config.load()
    sim_path = config.project_root / "simulations" / sim_id
    simulation = load_simulation(sim_path)
    
    # Resolve output config with simulation overrides
    output_config = config.resolve_output(simulation)
    
    # Build narrators list
    narrators: list[Narrator] = []
    
    # Console narrator (always, respects show_narratives)
    narrators.append(ConsoleNarrator(show_narratives=output_config.console.show_narratives))
    
    # Telegram narrator (if enabled and mode != none)
    if output_config.telegram.enabled and output_config.telegram.mode != "none":
        if not config.telegram_bot_token:
            typer.echo("Warning: Telegram enabled but TELEGRAM_BOT_TOKEN not set", err=True)
        else:
            from src.utils.telegram_client import TelegramClient
            
            client = TelegramClient(config.telegram_bot_token)
            narrators.append(TelegramNarrator(
                client=client,
                chat_id=output_config.telegram.chat_id,
                mode=output_config.telegram.mode,
                group_intentions=output_config.telegram.group_intentions,
                group_narratives=output_config.telegram.group_narratives,
            ))
    
    runner = TickRunner(config, narrators)
    await runner.run_tick(simulation, sim_path)
```

### Error Handling

- Отсутствует `TELEGRAM_BOT_TOKEN` при `telegram.enabled=true` → warning, продолжаем без Telegram
- Ошибки TelegramNarrator → логируем, симуляция продолжается
- Telegram недоступен → retry в TelegramClient, после исчерпания попыток — warning

### Обновление .env.example

```bash
# OpenAI API key (required)
OPENAI_API_KEY=sk-...

# Telegram bot token (optional, for TelegramNarrator)
TELEGRAM_BOT_TOKEN=123456789:ABC...
```

### Тесты

- Integration test: run с telegram.enabled=true но без токена → warning, tick завершается
- Integration test: run с telegram.enabled=true и mock client → narrator вызывается
- Unit test cli: проверка создания TelegramNarrator при правильном конфиге

### Артефакты

- Задание: `docs/tasks/TS-BACKLOG-005-INTEGRATION-001.md`
- Отчёт: `docs/tasks/TS-BACKLOG-005-INTEGRATION-001_REPORT.md`
- Модули: `src/cli.py` (обновить)
- Конфиг: `.env.example` (обновить)
- Спецификации: `docs/specs/core_cli.md` (обновить)
- Спецификации: `docs/specs/core_runner.md` (обновить)
- Тесты: `tests/unit/test_cli.py` (обновить)
- Тесты: `tests/integration/test_telegram_integration.py` (новый)

---

## Зависимости между этапами

```
Этап 1 (Config) 
    ↓
Этап 2 (TelegramClient) ← требует бота и канал для integration tests
    ↓
Этап 3 (TelegramNarrator)
    ↓
Этап 4 (Integration)
```

**Перед Этапом 2:** Необходимо создать Telegram бота через @BotFather и тестовый канал, добавить бота администратором канала.

---

## Технические детали

### Telegram Bot API

- Endpoint: `https://api.telegram.org/bot<token>/sendMessage`
- Метод: POST
- Content-Type: application/json
- Параметры: `chat_id`, `text`, `parse_mode`
- Лимит текста: 4096 символов
- Rate limits: 30 msg/sec в каналы, 20 msg/sec в группы

### HTML форматирование

- `<b>bold</b>`
- `<i>italic</i>`
- `<code>monospace</code>`
- `<pre>preformatted</pre>`
- Спецсимволы экранировать: `<`, `>`, `&`

### chat_id

- Всегда числовой (строка с цифрами)
- Никаких `@channel_name`
- Для каналов — отрицательное число (например, `-1001234567890`)
