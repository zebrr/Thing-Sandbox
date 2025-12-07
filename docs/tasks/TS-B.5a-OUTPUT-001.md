# TS-B.5a-OUTPUT-001: Расширить конфигурацию вывода и данные фаз

## References

**Обязательно изучить перед началом:**
- `docs/specs/core_config.md` — текущая спецификация конфига
- `docs/specs/util_llm.md` — текущая спецификация LLM клиента
- `docs/specs/phase_common.md` — текущая спецификация PhaseResult
- `docs/Thing' Sandbox LLM Usage Tracking.md` — документация по учёту токенов

**Код для изучения:**
- `src/config.py` — текущая реализация конфига
- `src/utils/llm.py` — текущая реализация LLM клиента
- `src/phases/common.py` — текущая реализация PhaseResult
- `src/phases/phase1.py`, `phase2a.py`, `phase2b.py`, `phase4.py` — как фазы возвращают результат

## Context

**Текущее состояние:**
- Все 4 фазы реализованы и работают с LLM
- `BatchStats` содержит только агрегированную статистику (total_tokens, reasoning_tokens, etc.)
- `PhaseResult` содержит только success, data, error — без статистики
- Reasoning summary извлекается в адаптере (`ResponseDebugInfo.reasoning_summary`), но теряется в `LLMClient`
- Конфигурация не имеет секции для управления выводом (console/file/telegram)

**Цель задачи:**
1. Добавить секцию `[output]` в конфиг для управления выводом
2. Расширить `BatchStats` для хранения per-request данных (reasoning_summary, usage per request)
3. Добавить `stats` в `PhaseResult` чтобы Runner мог собирать детальную статистику

**Зачем это нужно:**
- Для TickLogger (B.5b) — детальное логирование тиков требует reasoning summaries и per-request статистику
- Для управления выводом — отключение нарративов в консоли когда основной вывод в телегу

## Steps

### 1. Обновить config.toml

Добавить секцию `[output]` в конец файла:

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

### 2. Обновить src/config.py

Добавить Pydantic модели для OutputConfig:

```python
class ConsoleOutputConfig(BaseModel):
    """Console output configuration."""
    enabled: bool = True
    show_narratives: bool = True


class FileOutputConfig(BaseModel):
    """File output configuration (TickLogger)."""
    enabled: bool = True


class TelegramOutputConfig(BaseModel):
    """Telegram output configuration (future)."""
    enabled: bool = False
    chat_id: str = ""


class OutputConfig(BaseModel):
    """Output configuration section."""
    console: ConsoleOutputConfig = Field(default_factory=ConsoleOutputConfig)
    file: FileOutputConfig = Field(default_factory=FileOutputConfig)
    telegram: TelegramOutputConfig = Field(default_factory=TelegramOutputConfig)
```

Добавить атрибут в класс `Config`:
```python
output: OutputConfig = Field(default_factory=OutputConfig)
```

### 3. Обновить src/utils/llm.py

**3.1. Добавить импорт:**
```python
from dataclasses import dataclass, field
from src.utils.llm_adapters.base import ResponseUsage  # уже есть
```

**3.2. Добавить RequestResult dataclass:**
```python
@dataclass
class RequestResult:
    """Per-request result for detailed logging.
    
    Captures entity_key, success status, usage statistics, 
    reasoning summary, and error message for each request in a batch.
    """
    entity_key: str | None
    success: bool
    usage: ResponseUsage | None = None
    reasoning_summary: list[str] | None = None
    error: str | None = None
```

**3.3. Расширить BatchStats:**
```python
@dataclass
class BatchStats:
    """Statistics for the last batch execution."""
    total_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    # NEW: per-request details for detailed logging
    results: list[RequestResult] = field(default_factory=list)
```

**3.4. Обновить _execute_one() для сохранения reasoning_summary:**

В методе `_execute_one()` после успешного выполнения, добавить RequestResult в stats:

```python
# После строки self._last_batch_stats.success_count += 1
self._last_batch_stats.results.append(
    RequestResult(
        entity_key=request.entity_key,
        success=True,
        usage=response.usage,
        reasoning_summary=response.debug.reasoning_summary,
    )
)
```

В блоке except (перед raise), добавить RequestResult для ошибки:
```python
self._last_batch_stats.results.append(
    RequestResult(
        entity_key=request.entity_key,
        success=False,
        error=str(e) if isinstance(e, Exception) else str(e),
    )
)
```

**3.5. Обновить create_response() аналогично:**

После успешного выполнения добавить:
```python
self._last_batch_stats.results.append(
    RequestResult(
        entity_key=entity_key,
        success=True,
        usage=response.usage,
        reasoning_summary=response.debug.reasoning_summary,
    )
)
```

### 4. Обновить src/phases/common.py

Добавить импорт и поле stats:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.utils.llm import BatchStats


@dataclass
class PhaseResult:
    """Result of phase execution.
    
    Attributes:
        success: Whether the phase completed successfully.
        data: Phase-specific output data.
        error: Error message if success is False.
        stats: LLM batch statistics (tokens, reasoning summaries).
    """
    success: bool
    data: Any
    error: str | None = None
    stats: BatchStats | None = None
```

### 5. Обновить фазы 1, 2a, 2b, 4

В каждой фазе изменить return statement:

**phase1.py** (в конце execute):
```python
return PhaseResult(
    success=True, 
    data=intentions,
    stats=llm_client.get_last_batch_stats(),
)
```

**phase2a.py** (в конце execute):
```python
return PhaseResult(
    success=True, 
    data=results,
    stats=llm_client.get_last_batch_stats(),
)
```

**phase2b.py** (в конце execute):
```python
return PhaseResult(
    success=True, 
    data=results,
    stats=llm_client.get_last_batch_stats(),
)
```

**phase4.py** (в конце execute):
```python
return PhaseResult(
    success=True, 
    data=None,
    stats=llm_client.get_last_batch_stats(),
)
```

**Важно:** Phase 3 не использует LLM, поэтому оставляем `stats=None`.

### 6. Обновить спецификации

**docs/specs/core_config.md:**
- Добавить секцию для OutputConfig и вложенных моделей
- Добавить описание `Config.output` атрибута
- Добавить примеры использования
- Добавить тесты в Test Coverage

**docs/specs/util_llm.md:**
- Добавить описание `RequestResult` dataclass
- Обновить описание `BatchStats` (добавить поле `results`)
- Обновить примеры использования

**docs/specs/phase_common.md:**
- Добавить описание поля `stats: BatchStats | None`
- Обновить примеры

## Testing

### Активация venv
```bash
source venv/bin/activate  # macOS
```

### Проверка качества кода
```bash
ruff check src/
ruff format src/
mypy src/
```

### Запуск тестов
```bash
# Все тесты
pytest

# Только новые/обновлённые тесты
pytest tests/unit/test_config.py -v
pytest tests/unit/test_llm.py -v
pytest tests/unit/test_phases_common.py -v
```

### Ожидаемые результаты тестов

**test_config.py — новые тесты:**
- test_output_config_defaults — дефолтные значения OutputConfig
- test_output_console_config — console.enabled, console.show_narratives
- test_output_file_config — file.enabled
- test_output_telegram_config — telegram.enabled, telegram.chat_id
- test_output_config_from_toml — загрузка из config.toml

**test_llm.py — новые тесты:**
- test_request_result_success — создание успешного RequestResult
- test_request_result_failure — создание RequestResult с ошибкой
- test_batch_stats_results_populated — results заполняется при batch
- test_batch_stats_results_contains_reasoning — reasoning_summary сохраняется
- test_create_response_populates_results — single request тоже заполняет results

**test_phases_common.py — новые тесты:**
- test_phase_result_with_stats — PhaseResult с BatchStats
- test_phase_result_stats_default_none — stats по умолчанию None

## Deliverables

1. **Обновлённые файлы:**
   - `config.toml` — секция [output]
   - `src/config.py` — OutputConfig и вложенные модели
   - `src/utils/llm.py` — RequestResult, расширенный BatchStats
   - `src/phases/common.py` — поле stats в PhaseResult
   - `src/phases/phase1.py` — добавить stats в return
   - `src/phases/phase2a.py` — добавить stats в return
   - `src/phases/phase2b.py` — добавить stats в return
   - `src/phases/phase4.py` — добавить stats в return

2. **Обновлённые спецификации:**
   - `docs/specs/core_config.md`
   - `docs/specs/util_llm.md`
   - `docs/specs/phase_common.md`

3. **Обновлённые тесты:**
   - `tests/unit/test_config.py`
   - `tests/unit/test_llm.py`
   - `tests/unit/test_phases_common.py`

4. **Отчёт:** `docs/tasks/TS-B.5a-OUTPUT-001_REPORT.md`
