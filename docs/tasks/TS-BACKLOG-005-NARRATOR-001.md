# TS-BACKLOG-005-NARRATOR-001: TelegramNarrator Implementation

## References

Изучить перед началом работы:

- `docs/Thing' Sandbox Architecture.md` — общая архитектура, эмодзи логгера
- `docs/Thing' Sandbox BACKLOG-005 Workplan.md` — Этап 3 (полное описание)
- `docs/specs/core_narrators.md` — протокол Narrator, ConsoleNarrator
- `docs/specs/core_runner.md` — как runner вызывает narrators
- `docs/specs/util_telegram_client.md` — TelegramClient API
- `src/runner.py` — PhaseData, TickReport, fire-and-forget паттерн
- `src/narrators.py` — текущая реализация ConsoleNarrator

## Context

**Статус:** Этапы 1-2 завершены. TelegramClient готов, конфигурация с merge-логикой работает.

**Цель:** Реализовать TelegramNarrator — бизнес-логику форматирования и отправки сообщений в Telegram по мере выполнения тика.

**Ключевая идея:** TelegramNarrator использует lifecycle методы протокола Narrator:
- `on_tick_start` — сохраняет simulation для name lookups
- `on_phase_complete("phase1", ...)` — отправляет intentions (если mode=full/full_stats)
- `on_phase_complete("phase2a", ...)` — сохраняет stats для суммирования с phase2b
- `on_phase_complete("phase2b", ...)` — отправляет narratives + combined stats
- `output()` — no-op (всё уже отправлено)

Runner вызывает `on_phase_complete` через fire-and-forget (`asyncio.create_task`), поэтому отправка идёт параллельно с выполнением следующих фаз.

## Steps

### 1. Добавить helper функцию `escape_html` в `src/narrators.py`

```python
def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram.
    
    Escapes: & < >
    
    Args:
        text: Raw text that may contain HTML special characters.
    
    Returns:
        Text safe for Telegram HTML parse mode.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```

### 2. Реализовать класс `TelegramNarrator` в `src/narrators.py`

```python
class TelegramNarrator:
    """Sends tick updates to Telegram channel via lifecycle methods.
    
    Implements Narrator protocol. Uses async on_phase_complete to send
    intentions after Phase 1 and narratives after Phase 2b.
    
    Runner uses fire-and-forget pattern: creates tasks for on_phase_complete
    but doesn't await immediately. All tasks awaited at end of tick.
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
            client: TelegramClient instance (from utils.telegram_client).
            chat_id: Target chat/channel ID.
            mode: Output mode (narratives, narratives_stats, full, full_stats).
            group_intentions: Group all intentions in one message.
            group_narratives: Group all narratives in one message.
        """
```

**Атрибуты экземпляра:**
- `_client`, `_chat_id`, `_mode`, `_group_intentions`, `_group_narratives` — из __init__
- `_simulation: Simulation | None` — устанавливается в on_tick_start
- `_sim_id: str` — устанавливается в on_tick_start  
- `_tick_number: int` — устанавливается в on_tick_start
- `_phase2a_stats: BatchStats | None` — накапливается для combined stats
- `_phase2a_duration: float` — накапливается для combined duration

**Методы:**

```python
async def on_tick_start(self, sim_id: str, tick_number: int, simulation: Simulation) -> None:
    """Store simulation reference for name lookups."""
    # Сохранить simulation, sim_id, tick_number
    # Сбросить _phase2a_stats и _phase2a_duration

async def on_phase_complete(self, phase_name: str, phase_data: PhaseData) -> None:
    """Send messages after relevant phases."""
    # phase1 + mode in (full, full_stats) → _send_intentions(phase_data)
    # phase2a → сохранить stats и duration для суммирования
    # phase2b → _send_narratives(phase_data)

def output(self, report: TickReport) -> None:
    """No-op — all messages sent in on_phase_complete."""
    pass

async def _send_intentions(self, phase_data: PhaseData) -> None:
    """Format and send intentions to Telegram."""
    # См. форматы ниже

async def _send_narratives(self, phase_data: PhaseData) -> None:
    """Format and send narratives to Telegram."""
    # См. форматы ниже
```

### 3. Форматы сообщений

**Важно:** Контент из LLM (intentions, narratives, имена) — ВСЕГДА через `escape_html()`. Наша разметка (`<b>`, `<i>`) — без экранирования.

#### Intentions (mode=full/full_stats)

**Grouped (group_intentions=true):**
```html
🎯 <b>{sim_id} — tick #{tick_number} | Intentions</b>

<b>{char_name}:</b>
{intention}

<b>{char_name}:</b>
{intention}

───
📊 <i>Phase 1: {total_tokens:,} tok · {reasoning_tokens:,} reason · {duration:.1f}s</i>
```

**Per-character (group_intentions=false):**

N сообщений. Stats footer только на последнем:
```html
🎯 <b>{sim_id} — tick #{tick_number} | {char_name}</b>

{intention}
```

Последнее сообщение добавляет footer:
```html
🎯 <b>{sim_id} — tick #{tick_number} | {char_name}</b>

{intention}

───
📊 <i>Phase 1: {total_tokens:,} tok · {reasoning_tokens:,} reason · {duration:.1f}s</i>
```

#### Narratives (все режимы кроме none)

**Grouped (group_narratives=true):**
```html
📖 <b>{sim_id} — tick #{tick_number} | Narratives</b>

<b>{loc_name}</b>
{narrative}

<b>{loc_name}</b>
{narrative}

───
📊 <i>Phase 2: {total_tokens:,} tok · {reasoning_tokens:,} reason · {duration:.1f}s</i>
```

**Per-location (group_narratives=false):**

M сообщений. Stats footer только на последнем:
```html
📖 <b>{sim_id} — tick #{tick_number} | {loc_name}</b>

{narrative}
```

#### Stats footer

- Показывается только для режимов `_stats` (narratives_stats, full_stats)
- Только на последнем сообщении каждого типа
- Для narratives: сумма Phase 2a + Phase 2b (stats и duration)
- Разделитель `───` (три em-dash, U+2500)

### 4. Логирование

```python
logger = logging.getLogger(__name__)
```

**После успешной отправки intentions:**
```python
logger.info("Sent %d intentions", count)
# Выведет: 💬 telegram: Sent 2 intentions
```

**После успешной отправки narratives:**
```python
logger.info("Sent %d narratives", count)
# Выведет: 💬 telegram: Sent 3 narratives
```

**При ошибке отправки:**
```python
logger.warning("Failed to send intention for %s", char_id)
logger.warning("Failed to send narrative for %s", loc_id)
```

**Примечание:** Эмодзи 💬 добавляется автоматически через logging format (см. архитектуру). В коде пишем просто текст.

**Важно:** Логируем количество бизнес-объектов (intentions/narratives), а не HTTP-запросов. Сколько сообщений реально ушло в Telegram — детали TelegramClient.

### 5. Обработка ошибок

- Ошибки `TelegramClient.send_message()` → логируем WARNING, продолжаем
- Если `self._simulation is None` в on_phase_complete → логируем WARNING, пропускаем
- Lifecycle методы НЕ бросают исключения наружу (runner изолирует, но лучше не полагаться)
- При ошибке одного сообщения — продолжаем со следующим

### 6. Источники данных

**В on_phase_complete("phase1", phase_data):**
- `phase_data.data` — `dict[str, IntentionResponse]` (char_id → response)
- `phase_data.stats` — `BatchStats` (total_tokens, reasoning_tokens)
- `phase_data.duration` — `float` (секунды)
- `self._simulation.characters[char_id].identity.name` — имя персонажа

**В on_phase_complete("phase2a", phase_data):**
- Сохранить `phase_data.stats` в `self._phase2a_stats`
- Сохранить `phase_data.duration` в `self._phase2a_duration`

**В on_phase_complete("phase2b", phase_data):**
- `phase_data.data` — `dict[str, NarrativeResponse]` (loc_id → response)
- Combined stats: `phase_data.stats + self._phase2a_stats`
- Combined duration: `phase_data.duration + self._phase2a_duration`
- `self._simulation.locations[loc_id].identity.name` — имя локации

### 7. Обновить импорты в `src/narrators.py`

Добавить:
```python
from src.utils.telegram_client import TelegramClient
```

И в TYPE_CHECKING блок (если нужно для type hints):
```python
from src.utils.llm import BatchStats
```

### 8. Обновить спецификацию `docs/specs/core_narrators.md`

Добавить:
- Документацию `escape_html()` в Public API
- Полную документацию `TelegramNarrator` (конструктор, методы)
- Формат вывода для Telegram
- Тесты для TelegramNarrator

### 9. Обновить `__all__` в `src/narrators.py`

```python
__all__ = ["Narrator", "ConsoleNarrator", "TelegramNarrator", "escape_html"]
```

## Testing

### Активация окружения

```bash
source venv/bin/activate
```

### Проверка качества кода

```bash
ruff check src/narrators.py
ruff format src/narrators.py
mypy src/narrators.py
```

### Unit тесты

Добавить в `tests/unit/test_narrators.py`:

**escape_html:**
- `test_escape_html_ampersand` — `&` → `&amp;`
- `test_escape_html_less_than` — `<` → `&lt;`
- `test_escape_html_greater_than` — `>` → `&gt;`
- `test_escape_html_combined` — `<b>&</b>` → `&lt;b&gt;&amp;&lt;/b&gt;`
- `test_escape_html_no_change` — обычный текст без изменений

**TelegramNarrator с mocked TelegramClient:**
- `test_telegram_narrator_protocol` — satisfies Narrator protocol
- `test_on_tick_start_stores_simulation` — simulation сохраняется
- `test_on_tick_start_resets_phase2a_stats` — stats сбрасываются
- `test_on_phase_complete_phase1_sends_intentions` — intentions отправляются (mode=full)
- `test_on_phase_complete_phase1_skipped_for_narratives_mode` — не отправляет (mode=narratives)
- `test_on_phase_complete_phase2a_stores_stats` — stats сохраняются
- `test_on_phase_complete_phase2b_sends_narratives` — narratives отправляются
- `test_intentions_grouped_single_message` — один вызов send_message (group=true)
- `test_intentions_per_character_multiple_messages` — N вызовов (group=false)
- `test_narratives_grouped_single_message` — один вызов send_message (group=true)
- `test_narratives_per_location_multiple_messages` — M вызовов (group=false)
- `test_stats_footer_only_for_stats_modes` — footer есть для full_stats, нет для full
- `test_stats_footer_only_on_last_message` — footer на последнем сообщении
- `test_phase2_stats_combined` — stats из phase2a + phase2b суммируются
- `test_output_is_noop` — output() ничего не делает
- `test_error_handling_continues` — ошибка client не останавливает отправку
- `test_missing_simulation_logs_warning` — warning если simulation is None

### Запуск тестов

```bash
pytest tests/unit/test_narrators.py -v
```

### Полный прогон

```bash
pytest
```

## Deliverables

- [ ] `src/narrators.py` — добавлены `escape_html()` и `TelegramNarrator`
- [ ] `docs/specs/core_narrators.md` — обновлена спецификация
- [ ] `tests/unit/test_narrators.py` — добавлены тесты
- [ ] Все проверки качества пройдены (ruff, mypy)
- [ ] Все тесты проходят
- [ ] Отчёт: `docs/tasks/TS-BACKLOG-005-NARRATOR-001_REPORT.md`
