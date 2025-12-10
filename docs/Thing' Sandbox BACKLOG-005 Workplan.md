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

Форматирование и отправка сообщений в Telegram по мере выполнения тика. Реализует `Narrator` protocol с использованием lifecycle методов.
Добавляется в `src/narrators.py` согласно архитектуре.

**STATUS: не начат**

### References

- Архитектура: `docs/Thing' Sandbox Architecture.md`
- Telegram API Reference: `docs/Thing' Sandbox Telegram API Reference.md`
- Спецификация Config: `docs/specs/core_config.md`
- Спецификация TelegramClient: `docs/specs/util_telegram_client.md`
- Спецификация Narrators: `docs/specs/core_narrators.md`
- Спецификация Runner: `docs/specs/core_runner.md`

### Задачи

1. Обновить спецификацию `docs/specs/core_narrators.md`
2. Реализовать `TelegramNarrator` в `src/narrators.py`
3. Написать тесты

### Архитектура: Lifecycle методы

TelegramNarrator использует lifecycle методы протокола Narrator для отправки сообщений **по мере выполнения тика**, а не в конце:

```
on_tick_start(sim_id, tick_number, simulation)
    → Сохраняет simulation в self._simulation для доступа к именам
    → Сохраняет sim_id, tick_number для заголовков

on_phase_complete("phase1", phase_data)
    → Отправляет intentions (если mode=full/full_stats)
    → Данные: phase_data.data = dict[str, IntentionResponse]
    → Имена персонажей: self._simulation.characters[id].identity.name

on_phase_complete("phase2b", phase_data)
    → Отправляет narratives
    → Данные: phase_data.data = dict[str, NarrativeResponse]
    → Имена локаций: self._simulation.locations[id].identity.name

output(report)
    → No-op (всё уже отправлено в on_phase_complete)
```

**Преимущество:** Пользователь видит intentions сразу после Phase 1, не дожидаясь завершения всего тика.

### Класс TelegramNarrator

```python
class TelegramNarrator:
    """Sends tick updates to Telegram channel via lifecycle methods.
    
    Implements Narrator protocol. Uses on_phase_complete to send
    intentions after Phase 1 and narratives after Phase 2b.
    """
    
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
        self._client = client
        self._chat_id = chat_id
        self._mode = mode
        self._group_intentions = group_intentions
        self._group_narratives = group_narratives
        
        # Set by on_tick_start, used in on_phase_complete
        self._simulation: Simulation | None = None
        self._sim_id: str = ""
        self._tick_number: int = 0
        
        # Accumulate stats for phase2 (2a + 2b)
        self._phase2a_stats: BatchStats | None = None
        self._phase2a_duration: float = 0.0
    
    def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
        """Store simulation reference for name lookups."""
        self._simulation = simulation
        self._sim_id = sim_id
        self._tick_number = tick_number
        self._phase2a_stats = None
        self._phase2a_duration = 0.0
    
    def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
        """Send messages after relevant phases."""
        if phase_name == "phase1" and self._mode in ("full", "full_stats"):
            self._send_intentions(phase_data)
        elif phase_name == "phase2a":
            # Store for combined stats with phase2b
            self._phase2a_stats = phase_data.stats
            self._phase2a_duration = phase_data.duration
        elif phase_name == "phase2b":
            self._send_narratives(phase_data)
    
    def output(self, report: TickReport) -> None:
        """No-op — all messages sent in on_phase_complete."""
        pass
```

### Async в sync контексте

Runner вызывает lifecycle методы синхронно. TelegramClient — async.

**Решение:** Использовать `asyncio.get_event_loop().run_until_complete()` внутри lifecycle методов. Runner уже запущен в async контексте через `asyncio.run()` в CLI, но lifecycle методы вызываются синхронно.

```python
def _send_intentions(self, phase_data: PhaseData) -> None:
    """Send intentions to Telegram."""
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._send_intentions_async(phase_data))
    except Exception as e:
        logger.warning("Failed to send intentions: %s", e)
```

**Альтернатива (если run_until_complete не работает):** `asyncio.run()` в отдельном потоке:

```python
def _send_intentions(self, phase_data: PhaseData) -> None:
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, self._send_intentions_async(phase_data))
            future.result(timeout=30.0)
    except Exception as e:
        logger.warning("Failed to send intentions: %s", e)
```

### Helper функция

```python
def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram.
    
    Escapes: < > &
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```

### Источники данных

**В on_phase_complete("phase1", phase_data):**
- `phase_data.data` — `dict[str, IntentionResponse]` (char_id → response)
- `phase_data.stats` — BatchStats
- `phase_data.duration` — float (секунды)
- `self._simulation.characters[char_id].identity.name` — имя персонажа

**В on_phase_complete("phase2b", phase_data):**
- `phase_data.data` — `dict[str, NarrativeResponse]` (loc_id → response)
- `phase_data.stats` + `self._phase2a_stats` — суммарная статистика Phase 2
- `phase_data.duration` + `self._phase2a_duration` — суммарное время Phase 2
- `self._simulation.locations[loc_id].identity.name` — имя локации

### Форматы сообщений

**Intentions (mode=full/full_stats, group_intentions=true):**
```html
🎯 <b>demo-sim — tick #42 | Intentions</b>

<b>Ogilvy:</b>
Approach the cylinder to examine it more closely...

<b>Henderson:</b>
Interview locals about what they witnessed...

───
📊 <i>Phase 1: 4,200 tok · 1,100 reason · 2.1s</i>
```

**Intentions (mode=full/full_stats, group_intentions=false):**

Отправляется N сообщений. Stats footer только на последнем:
```html
🎯 <b>demo-sim — tick #42 | Ogilvy</b>

Approach the cylinder to examine it more closely...
```

Последнее сообщение:
```html
🎯 <b>demo-sim — tick #42 | Henderson</b>

Interview locals about what they witnessed...

───
📊 <i>Phase 1: 4,200 tok · 1,100 reason · 2.1s</i>
```

**Narratives (group_narratives=true):**
```html
📖 <b>demo-sim — tick #42 | Narratives</b>

<b>Horsell Common</b>
Ogilvy cautiously approaches the pit...

<b>The Red Lion Inn</b>
Henderson scribbles notes furiously...

───
📊 <i>Phase 2: 8,250 tok · 2,100 reason · 4.1s</i>
```

**Narratives (group_narratives=false):**

Отправляется M сообщений. Stats footer только на последнем:
```html
📖 <b>demo-sim — tick #42 | Horsell Common</b>

Ogilvy cautiously approaches the pit...
```

Последнее сообщение:
```html
📖 <b>demo-sim — tick #42 | The Red Lion Inn</b>

Henderson scribbles notes furiously...

───
📊 <i>Phase 2: 8,250 tok · 2,100 reason · 4.1s</i>
```

### Stats Footer

**Показывается:**
- Только для режимов `_stats` (narratives_stats, full_stats)
- Только на последнем сообщении каждого типа (intentions / narratives)
- Для narratives: сумма Phase 2a + Phase 2b stats и durations

**Формат:**
```html

───
📊 <i>Phase N: 12,450 tok · 3,200 reason · 6.2s</i>
```

### Логирование

```python
logger = logging.getLogger(__name__)
```

- **DEBUG**: форматирование сообщений
- **INFO**: `📨 telegram: Sent 2 intentions to chat -100123`
- **INFO**: `📨 telegram: Sent 1 narrative to chat -100123`
- **WARNING**: ошибка отправки (продолжаем работу)

### Обработка ошибок

- Ошибки TelegramClient логируются как WARNING
- Lifecycle методы НЕ бросают исключения (изолированы в runner)
- При ошибке отправки — продолжаем со следующим сообщением
- Если `self._simulation` is None в on_phase_complete — логируем WARNING, пропускаем

### Тесты

**Unit тесты с mocked TelegramClient:**
- `test_on_tick_start_stores_simulation` — simulation сохраняется
- `test_on_phase_complete_phase1_sends_intentions` — intentions отправляются после phase1
- `test_on_phase_complete_phase1_skipped_for_narratives_mode` — mode=narratives не отправляет intentions
- `test_on_phase_complete_phase2b_sends_narratives` — narratives отправляются после phase2b
- `test_intentions_grouped` — один вызов send_message для intentions
- `test_intentions_per_character` — N вызовов send_message
- `test_narratives_grouped` — один вызов send_message для narratives
- `test_narratives_per_location` — M вызовов send_message
- `test_stats_footer_only_on_last` — footer на последнем сообщении
- `test_stats_footer_only_for_stats_modes` — нет footer для non-stats режимов
- `test_phase2_stats_combined` — stats суммируются из phase2a и phase2b
- `test_escape_html` — экранирование < > &
- `test_error_handling` — ошибка client не бросает exception
- `test_output_is_noop` — output() ничего не делает
- `test_narrator_protocol` — TelegramNarrator satisfies Narrator protocol

### Артефакты

- Задание: `docs/tasks/TS-BACKLOG-005-NARRATOR-001.md`
- Отчёт: `docs/tasks/TS-BACKLOG-005-NARRATOR-001_REPORT.md`
- Спецификация: `docs/specs/core_narrators.md` (обновить)
- Модуль: `src/narrators.py` (обновить — добавить TelegramNarrator, escape_html)
- Тесты: `tests/unit/test_narrators.py` (обновить)

---

## Этап 4: Интеграция в CLI

Подключение TelegramNarrator в CLI. Runner не меняется — он уже вызывает все narrators через `_call_narrators()`.

**STATUS: не начат**

### References

- Спецификация Config: `docs/specs/core_config.md`
- Спецификация TelegramClient: `docs/specs/util_telegram_client.md`
- Спецификация Narrators: `docs/specs/core_narrators.md`
- Спецификация CLI: `docs/specs/core_cli.md`

### Изменения в cli.py

```python
@app.command()
def run(sim_id: str) -> None:
    config = Config.load()
    sim_path = config.project_root / "simulations" / sim_id
    simulation = load_simulation(sim_path)
    
    output_config = config.resolve_output(simulation)
    
    # Build narrators list
    narrators: list[Narrator] = []
    
    # Console narrator (always)
    narrators.append(ConsoleNarrator(show_narratives=output_config.console.show_narratives))
    
    # Telegram narrator (if enabled and mode != none)
    if output_config.telegram.enabled and output_config.telegram.mode != "none":
        if not config.telegram_bot_token:
            typer.echo("Warning: Telegram enabled but TELEGRAM_BOT_TOKEN not set", err=True)
        else:
            from src.narrators import TelegramNarrator
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
    asyncio.run(runner.run_tick(simulation, sim_path))
```

### Обновление .env.example

```bash
# OpenAI API key (required)
OPENAI_API_KEY=sk-...

# Telegram bot token (optional, for TelegramNarrator)
TELEGRAM_BOT_TOKEN=123456789:ABC...
```

### Error Handling

- Отсутствует `TELEGRAM_BOT_TOKEN` при `telegram.enabled=true` → warning, продолжаем без Telegram
- Ошибки TelegramNarrator → логируем, симуляция продолжается (runner изолирует ошибки narrators)
- Telegram недоступен → retry в TelegramClient, после исчерпания попыток — warning

### Тесты

- `test_cli_creates_telegram_narrator` — при правильном конфиге TelegramNarrator добавляется в narrators
- `test_cli_warns_no_token` — warning если enabled но нет токена
- `test_cli_telegram_disabled` — TelegramNarrator не создаётся при enabled=false
- `test_cli_telegram_mode_none` — TelegramNarrator не создаётся при mode=none

### Артефакты

- Задание: `docs/tasks/TS-BACKLOG-005-INTEGRATION-001.md`
- Отчёт: `docs/tasks/TS-BACKLOG-005-INTEGRATION-001_REPORT.md`
- Модули: `src/cli.py` (обновить)
- Конфиг: `.env.example` (обновить)
- Спецификации: `docs/specs/core_cli.md` (обновить)
- Тесты: `tests/unit/test_cli.py` (обновить)

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
