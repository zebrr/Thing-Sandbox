# TS-B.5b-TICKLOG-001: TickLogger

## References

- `docs/Thing' Sandbox Architecture.md` — структура логов, формат логирования
- `docs/Thing' Sandbox LLM Usage Tracking.md` — метрики, reasoning summary
- `docs/specs/core_runner.md` — текущая спека раннера
- `docs/specs/core_narrators.md` — текущая спека нарраторов
- `docs/specs/phase_common.md` — PhaseResult
- `docs/specs/util_llm.md` — BatchStats, RequestResult
- `src/runner.py` — текущая реализация
- `src/narrators.py` — текущая реализация
- `src/phases/phase2a.py` — MasterOutput, CharacterUpdate, LocationUpdate
- `src/phases/phase1.py` — IntentionResponse
- `src/phases/phase2b.py` — NarrativeResponse

## Context

B.5a готов — есть OutputConfig, RequestResult с reasoning_summary, BatchStats.results, PhaseResult.stats.

Нужно реализовать детальное логирование тиков в markdown-файлы. TickLogger записывает `logs/tick_NNNNNN.md` с полной информацией по всем фазам: токены, reasoning summaries, данные персонажей и локаций.

**ВАЖНО при реализации:**
- Phase 1, Phase 4 — поперсонажно (секция на каждого персонажа)
- Phase 2a, Phase 2b — полокационно (секция на каждую локацию, **включая пустые без персонажей!**)
- Phase 3 — и персонажи, и локации

## Log Format

Файл: `simulations/{sim_id}/logs/tick_NNNNNN.md` (6 цифр с ведущими нулями)

```markdown
# Tick 42

**Simulation:** demo-sim  
**Timestamp:** 2025-06-07 14:32  
**Duration:** 8.2s

## Summary

| Metric | Value |
|--------|-------|
| Total tokens | 4,566 |
| Reasoning tokens | 1,566 |
| Cached tokens | 890 |
| LLM requests | 8 |

## Phase 1: Intentions

**Duration:** 2.1s | **Tokens:** 1,200 (reasoning: 400)

### Ogilvy
- **Intention:** approach the cylinder cautiously
- **Reasoning:** _"The character's scientific curiosity would override fear..."_

### Henderson
- **Intention:** observe and take notes
- **Reasoning:** _"As a journalist, documenting is the priority..."_

## Phase 2a: Arbitration

**Duration:** 1.8s | **Tokens:** 1,500 (reasoning: 600)

### Horsell Common

**Characters:**
- **ogilvy:** location=horsell_common, state="anxious but determined", intent="examine the cylinder"
- **henderson:** location=horsell_common, state="alert", intent="document everything"

**Location:** moment="The cylinder surface glows faintly", description unchanged

**Reasoning:** _"No conflicts between intentions..."_

### Dark Forest

**Characters:** *(none)*

**Location:** moment unchanged, description unchanged

**Reasoning:** _"The forest remains undisturbed..."_

## Phase 2b: Narratives

**Duration:** 1.2s | **Tokens:** 800 (reasoning: 200)

### Horsell Common

> Ogilvy crept closer to the metallic cylinder, his heart pounding...

### Dark Forest

> The ancient oaks stood silent under the moonless sky...

## Phase 3: State Application

**Duration:** 0.01s | *(no LLM)*

### Characters
- **ogilvy:** location unchanged, state="anxious but determined", intent="examine the cylinder"
- **henderson:** location unchanged, state="alert", intent="document everything"

### Locations
- **horsell_common:** moment="The cylinder surface glows faintly", description unchanged
- **dark_forest:** moment unchanged, description unchanged

## Phase 4: Memory

**Duration:** 3.1s | **Tokens:** 1,066 (reasoning: 366)

### Ogilvy
- **New memory:** "I approached the cylinder..."
- **Cells:** 2/5 (no summarization)

### Henderson
- **New memory:** "Watched Ogilvy approach..."
- **Cells:** 5/5 → summarized
- **Reasoning:** _"Merging older observations about the crash site..."_
```

## Steps

### 1. Написать спецификацию `docs/specs/core_tick_logger.md`

Содержание:
- **PhaseData** — dataclass для хранения результата одной фазы:
  - `duration: float`
  - `stats: BatchStats | None`
  - `data: Any` — phase-specific (IntentionResponse dict, MasterOutput dict, etc.)
- **TickReport** — dataclass:
  - `sim_id: str`
  - `tick_number: int`
  - `timestamp: datetime`
  - `duration: float` (total)
  - `narratives: dict[str, str]`
  - `phases: dict[str, PhaseData]` — "phase1", "phase2a", "phase2b", "phase3", "phase4"
  - `simulation: Simulation` — для доступа к characters/locations при форматировании
- **TickLogger** класс:
  - `__init__(sim_path: Path)`
  - `write(report: TickReport) -> None` — создаёт logs/ если нет, пишет tick_NNNNNN.md

### 2. Реализовать `src/tick_logger.py`

- PhaseData, TickReport dataclasses
- TickLogger класс с методом write()
- Внутренние методы форматирования:
  - `_format_header(report)` — заголовок и summary таблица
  - `_format_phase1(phase_data, simulation)` — поперсонажно
  - `_format_phase2a(phase_data, simulation)` — полокационно
  - `_format_phase2b(phase_data, simulation)` — полокационно
  - `_format_phase3(phase_data, simulation)` — персонажи + локации
  - `_format_phase4(phase_data, simulation, pending_memories)` — поперсонажно
- Timestamp в локальном времени: `datetime.now().strftime("%Y-%m-%d %H:%M")`
- Reasoning форматировать как `_"текст..."_` (курсив в markdown)
- Если reasoning_summary это list[str] — джойнить через пробел

### 3. Обновить `src/runner.py`

- Добавить трекинг duration per phase (time.time() до и после каждой фазы)
- Сохранять PhaseData для каждой фазы (duration, stats, data)
- После всех фаз собирать TickReport
- Если `config.output.file.enabled`:
  - Создать TickLogger(sim_path)
  - Вызвать tick_logger.write(report)
- Передавать pending_memories в TickReport (нужно для Phase 4 — показать какая память добавилась)

### 4. Обновить `src/narrators.py`

- `ConsoleNarrator.__init__(show_narratives: bool = True)`
- Если `show_narratives=False` — не печатать секцию с нарративами (только header/footer и tick number)

### 5. Обновить `docs/specs/core_runner.md`

- Добавить шаг сборки TickReport после фаз
- Добавить шаг вызова TickLogger если config.output.file.enabled
- Описать PhaseData и как собираются данные

### 6. Обновить `docs/specs/core_narrators.md`

- Добавить параметр `show_narratives` для ConsoleNarrator
- Убрать упоминание FileNarrator из планов (заменён на TickLogger)

### 7. Написать тесты

**tests/unit/test_tick_logger.py:**
- test_tick_report_creation — создание TickReport
- test_tick_logger_creates_logs_dir — создаёт logs/ если не существует
- test_tick_logger_writes_file — записывает файл с правильным именем
- test_tick_logger_format_header — корректный заголовок и summary
- test_tick_logger_format_phase1 — поперсонажно, с reasoning
- test_tick_logger_format_phase2a — полокационно, включая пустые локации
- test_tick_logger_format_phase2b — полокационно, narratives в blockquote
- test_tick_logger_format_phase3 — персонажи + локации, unchanged
- test_tick_logger_format_phase4 — поперсонажно, cells count, summarization
- test_tick_logger_empty_reasoning — если reasoning None — не показывать строку
- test_tick_logger_tick_number_padding — tick 1 → tick_000001.md

**tests/unit/test_narrators.py (добавить):**
- test_console_narrator_show_narratives_false — не печатает нарративы
- test_console_narrator_show_narratives_default_true — по умолчанию печатает

**tests/integration/test_skeleton.py (добавить):**
- test_run_tick_creates_log_file — после тика создаётся logs/tick_000001.md
- test_run_tick_log_file_disabled — если config.output.file.enabled=False, файл не создаётся

## Testing

```bash
# Активировать venv
source venv/bin/activate

# Проверка качества кода
ruff check src/tick_logger.py src/runner.py src/narrators.py
ruff format src/tick_logger.py src/runner.py src/narrators.py
mypy src/tick_logger.py src/runner.py src/narrators.py

# Запуск тестов
pytest tests/unit/test_tick_logger.py -v
pytest tests/unit/test_narrators.py -v
pytest tests/integration/test_skeleton.py -v

# Все тесты
pytest
```

## Deliverables

1. **Спецификация:** `docs/specs/core_tick_logger.md` (новая)
2. **Модуль:** `src/tick_logger.py` (новый)
3. **Обновлённые модули:** `src/runner.py`, `src/narrators.py`
4. **Обновлённые спецификации:** `docs/specs/core_runner.md`, `docs/specs/core_narrators.md`
5. **Тесты:** `tests/unit/test_tick_logger.py` (новый), обновлённые `tests/unit/test_narrators.py`, `tests/integration/test_skeleton.py`
6. **Отчёт:** `docs/tasks/TS-B.5b-TICKLOG-001_REPORT.md`
