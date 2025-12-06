# TS-USAGE_REFACTOR-001: LLM Usage Tracking Implementation

## References

Обязательно изучить перед началом работы:

- `docs/Thing' Sandbox LLM Usage Tracking.md` — **основной документ требований**
- `docs/specs/util_llm.md` — текущая спека LLMClient
- `docs/specs/core_runner.md` — текущая спека Runner
- `src/utils/llm.py` — текущая реализация LLMClient
- `src/runner.py` — текущая реализация Runner

## Context

### Текущее состояние

LLMClient накапливает usage статистику в entity dicts, но:
1. Сохраняются только `input_tokens`, `output_tokens`, `total_requests`
2. `reasoning_tokens` и `cached_tokens` извлекаются адаптером, но теряются
3. Runner создаёт копии entities через `model_dump()` — изменения не попадают обратно в Simulation
4. Агрегат в `simulation._openai` не реализован
5. Логирование статистики по фазам отсутствует

### Цель

Реализовать полный цикл usage tracking согласно `docs/Thing' Sandbox LLM Usage Tracking.md`:
- Накопление `total_tokens`, `reasoning_tokens`, `cached_tokens`, `total_requests` по entities
- Синхронизация данных обратно в Simulation
- Агрегация в `simulation._openai`
- Логирование статистики по фазам и итога такта

### Важные уточнения

**Миграция данных:** НЕ требуется. Существующие симуляции могут содержать старый формат (`total_input_tokens`, `total_output_tokens`). Игнорируем — при первом запуске с новым кодом создастся новая структура. Старые поля останутся в JSON (extra="allow") и не мешают.

**Phase 2b:** Сейчас вызывается с `None` вместо LLMClient — это временный stub. НЕ исправлять в рамках этого задания. Инфраструктура (loc_entities, LLMClient для локаций) будет готова, Phase 2b реализуется отдельной задачей.

**Статистика по фазам:** Используем подход с `get_last_batch_stats()` в LLMClient (см. Step 2). НЕ вычисляем дельту по entity dicts — это избыточно сложно.

## Steps

### 1. LLMClient: расширить _accumulate_usage()

**Файл:** `src/utils/llm.py`

Изменить `_accumulate_usage()` — добавить накопление `reasoning_tokens` и `cached_tokens`:

```python
def _accumulate_usage(self, entity_key: str, usage: ResponseUsage) -> None:
    # ... existing code to get entity ...
    
    if "usage" not in entity["_openai"]:
        entity["_openai"]["usage"] = {
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "cached_tokens": 0,
            "total_requests": 0,
        }
    
    stats = entity["_openai"]["usage"]
    stats["total_tokens"] += usage.total_tokens
    stats["reasoning_tokens"] += usage.reasoning_tokens
    stats["cached_tokens"] += usage.cached_tokens
    stats["total_requests"] += 1
```

**Примечание:** `ResponseUsage` уже содержит все нужные поля (см. `llm_adapters/base.py`).

### 2. LLMClient: добавить get_last_batch_stats()

**Файл:** `src/utils/llm.py`

Добавить отслеживание статистики последнего batch для логирования:

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
```

В `LLMClient.__init__()`:
```python
self._last_batch_stats: BatchStats = BatchStats()
```

В `create_batch()` — сбрасывать и накапливать:
```python
async def create_batch(self, requests: list[LLMRequest]) -> list[BaseModel | LLMError]:
    # Reset stats at batch start
    self._last_batch_stats = BatchStats()
    
    # ... existing batch execution ...
    
    # In _execute_one or _process_result — accumulate stats
```

В `_execute_one()` после успешного выполнения:
```python
# Accumulate batch stats (for logging, separate from entity accumulation)
self._last_batch_stats.total_tokens += response.usage.total_tokens
self._last_batch_stats.reasoning_tokens += response.usage.reasoning_tokens
self._last_batch_stats.cached_tokens += response.usage.cached_tokens
self._last_batch_stats.request_count += 1
self._last_batch_stats.success_count += 1
```

При ошибке:
```python
self._last_batch_stats.request_count += 1
self._last_batch_stats.error_count += 1
```

Публичный метод:
```python
def get_last_batch_stats(self) -> BatchStats:
    """Get statistics from the last create_batch() call."""
    return self._last_batch_stats
```

Также добавить для `create_response()` (одиночный запрос):
```python
async def create_response(self, ...) -> T:
    # Reset stats
    self._last_batch_stats = BatchStats()
    
    # ... existing code ...
    
    # After success:
    self._last_batch_stats.total_tokens = response.usage.total_tokens
    self._last_batch_stats.reasoning_tokens = response.usage.reasoning_tokens
    self._last_batch_stats.cached_tokens = response.usage.cached_tokens
    self._last_batch_stats.request_count = 1
    self._last_batch_stats.success_count = 1
    
    return response.parsed
```

### 3. Runner: раздельные entity dicts для персонажей и локаций

**Файл:** `src/runner.py`

Изменить `_create_llm_client()` — создавать entity dicts и хранить как атрибуты:

```python
def _create_entity_dicts(self, simulation: Simulation) -> None:
    """Create entity dicts for LLM clients. Stored for later sync back."""
    self._char_entities = [c.model_dump() for c in simulation.characters.values()]
    self._loc_entities = [l.model_dump() for l in simulation.locations.values()]
```

Создавать отдельные LLMClient для разных фаз:
- Phase 1, Phase 4 — клиент с `self._char_entities`
- Phase 2a, Phase 2b — клиент с `self._loc_entities`

```python
def _create_char_llm_client(self, config: PhaseConfig) -> LLMClient:
    """Create LLM client for character phases (1, 4)."""
    adapter = OpenAIAdapter(config)
    return LLMClient(
        adapter=adapter,
        entities=self._char_entities,
        default_depth=config.response_chain_depth,
    )

def _create_loc_llm_client(self, config: PhaseConfig) -> LLMClient:
    """Create LLM client for location phases (2a, 2b)."""
    adapter = OpenAIAdapter(config)
    return LLMClient(
        adapter=adapter,
        entities=self._loc_entities,
        default_depth=config.response_chain_depth,
    )
```

### 4. Runner: синхронизация _openai обратно в Simulation

**Файл:** `src/runner.py`

Добавить метод синхронизации после выполнения фаз:

```python
def _sync_openai_data(self, simulation: Simulation) -> None:
    """Copy _openai data from entity dicts back to Simulation models."""
    for entity_dict in self._char_entities:
        char_id = entity_dict["identity"]["id"]
        if "_openai" in entity_dict and char_id in simulation.characters:
            # Pydantic models with extra="allow" accept arbitrary attributes
            simulation.characters[char_id].__dict__["_openai"] = entity_dict["_openai"]
    
    for entity_dict in self._loc_entities:
        loc_id = entity_dict["identity"]["id"]
        if "_openai" in entity_dict and loc_id in simulation.locations:
            simulation.locations[loc_id].__dict__["_openai"] = entity_dict["_openai"]
```

### 5. Runner: агрегация в simulation._openai

**Файл:** `src/runner.py`

Добавить метод агрегации usage по всем entities:

```python
def _aggregate_simulation_usage(self, simulation: Simulation) -> None:
    """Sum usage from all entities into simulation._openai."""
    totals = {
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cached_tokens": 0,
        "total_requests": 0,
    }
    
    # Sum from characters
    for char in simulation.characters.values():
        openai_data = char.__dict__.get("_openai")
        if openai_data and "usage" in openai_data:
            for key in totals:
                totals[key] += openai_data["usage"].get(key, 0)
    
    # Sum from locations
    for loc in simulation.locations.values():
        openai_data = loc.__dict__.get("_openai")
        if openai_data and "usage" in openai_data:
            for key in totals:
                totals[key] += openai_data["usage"].get(key, 0)
    
    # Store in simulation (will be saved by storage)
    simulation.__dict__["_openai"] = totals
```

### 6. Runner: логирование статистики

**Файл:** `src/runner.py`

#### 6.1. Логирование после каждой фазы

Использовать `llm_client.get_last_batch_stats()`:

```python
# После phase1
result1 = await execute_phase1(simulation, self._config, char_llm_client)
if not result1.success:
    raise PhaseError("phase1", result1.error or "Unknown error")

stats = char_llm_client.get_last_batch_stats()
logger.info(
    "🎭 phase1: Complete (%d chars, %s tokens, %s reasoning)",
    len(simulation.characters),
    f"{stats.total_tokens:,}",
    f"{stats.reasoning_tokens:,}",
)
```

Аналогично для phase2a, phase4. Phase2b и phase3 пока без LLM — логировать без статистики или пропустить.

#### 6.2. Накопление статистики такта

Хранить суммарную статистику такта для итогового лога:

```python
# В начале run_tick()
self._tick_stats = BatchStats()

# После каждой фазы с LLM
phase_stats = llm_client.get_last_batch_stats()
self._tick_stats.total_tokens += phase_stats.total_tokens
self._tick_stats.reasoning_tokens += phase_stats.reasoning_tokens
# ... и т.д.
```

#### 6.3. Итог такта

После сохранения:

```python
logger.info(
    "🎬 runner: Tick %d complete (%.1fs, %s tokens, %s reasoning)",
    tick_number,
    elapsed_time,
    f"{self._tick_stats.total_tokens:,}",
    f"{self._tick_stats.reasoning_tokens:,}",
)
```

### 7. Обновить run_tick() flow

**Файл:** `src/runner.py`

Интегрировать новые методы в `run_tick()`:

```python
async def run_tick(self, sim_id: str) -> TickResult:
    start_time = time.time()
    
    # ... load simulation, check status ...
    
    # Create entity dicts (stored as instance attributes)
    self._create_entity_dicts(simulation)
    
    # Reset tick stats
    self._tick_stats = BatchStats()
    
    # Execute phases (they mutate entity dicts via LLMClient)
    await self._execute_phases(simulation)
    
    # Sync _openai back to Simulation models
    self._sync_openai_data(simulation)
    
    # Aggregate into simulation._openai
    self._aggregate_simulation_usage(simulation)
    
    # ... increment tick, save ...
    
    elapsed_time = time.time() - start_time
    logger.info(
        "🎬 runner: Tick %d complete (%.1fs, %s tokens, %s reasoning)",
        tick_number,
        elapsed_time,
        f"{self._tick_stats.total_tokens:,}",
        f"{self._tick_stats.reasoning_tokens:,}",
    )
    
    # ... call narrators, return result ...
```

### 8. Storage: убедиться что _openai сохраняется

**Файл:** `src/utils/storage.py`

Модели уже используют `extra="allow"`, но нужно проверить что `model_dump()` включает extra fields. Если нет — добавить `mode="python"` или явно включить.

Проверить в тестах что `_openai` roundtrip работает.

## Testing

### Unit Tests

**Файл:** `tests/unit/test_llm.py` — дополнить:

- `test_accumulate_usage_all_fields` — проверить что все 4 поля накапливаются
- `test_accumulate_usage_creates_structure` — структура создаётся если отсутствует
- `test_get_last_batch_stats_after_batch` — статистика корректна после batch
- `test_get_last_batch_stats_after_single` — статистика корректна после create_response
- `test_get_last_batch_stats_with_errors` — error_count корректен при ошибках
- `test_batch_stats_reset_between_calls` — статистика сбрасывается между вызовами

**Файл:** `tests/unit/test_runner.py` — добавить:

- `test_sync_openai_data_characters` — данные копируются в персонажей
- `test_sync_openai_data_locations` — данные копируются в локации
- `test_aggregate_simulation_usage` — суммирование корректно
- `test_aggregate_empty_entities` — работает с пустыми entities
- `test_tick_logs_phase_stats` — проверить что логи вызываются (mock logger)

**Файл:** `tests/unit/test_storage.py` — дополнить:

- `test_roundtrip_preserves_openai` — `_openai` сохраняется и загружается

### Integration Tests

**Файл:** `tests/integration/test_usage_tracking.py` — новый файл:

- `test_usage_accumulated_after_tick` — после реального тика entity._openai содержит usage
- `test_simulation_openai_aggregated` — simulation._openai содержит сумму

## Deliverables

1. **Код:**
   - `src/utils/llm.py` — расширенный `_accumulate_usage()`, новый `BatchStats`, `get_last_batch_stats()`
   - `src/runner.py` — entity dicts management, sync, aggregation, logging

2. **Тесты:**
   - Дополненные unit tests в `test_llm.py`, `test_runner.py`, `test_storage.py`
   - Новый `test_usage_tracking.py` (integration)

3. **Спецификации — обновить:**
   - `docs/specs/util_llm.md` — описание новых полей в usage, BatchStats, get_last_batch_stats()
   - `docs/specs/core_runner.md` — новые методы, flow с sync/aggregation, logging

4. **Отчёт:**
   - `docs/tasks/TS-USAGE_REFACTOR-001_REPORT.md`

## Verification

```bash
# Активировать venv
source venv/bin/activate  # или . venv/bin/activate

# Проверка качества кода
ruff check src/utils/llm.py src/runner.py
ruff format src/utils/llm.py src/runner.py
mypy src/utils/llm.py src/runner.py

# Unit тесты
pytest tests/unit/test_llm.py -v
pytest tests/unit/test_runner.py -v
pytest tests/unit/test_storage.py -v

# Integration тесты (требует OPENAI_API_KEY)
pytest tests/integration/test_usage_tracking.py -v --integration

# Полный прогон
pytest tests/ -v
```

После тестов — ручная проверка:
```bash
python -m src.cli reset demo-sim
python -m src.cli tick demo-sim
# Проверить что в консоли видна статистика по фазам и итог
# Проверить simulations/demo-sim/simulation.json — должен содержать _openai
# Проверить simulations/demo-sim/characters/*.json — должны содержать _openai.usage
```
