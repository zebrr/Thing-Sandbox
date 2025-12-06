# TS-B.3b-PHASE2-001: Implement Phase 2a and 2b (Arbiter and Narrative)

## References

**Обязательно изучить перед началом:**
- `docs/specs/phase_2a.md` — спецификация Phase 2a (арбитр)
- `docs/specs/phase_2b.md` — спецификация Phase 2b (нарратив)
- `docs/specs/phase_1.md` — образец реализации фазы с LLM
- `src/phases/phase1.py` — образец кода фазы
- `docs/Thing' Sandbox Architecture.md` — раздел 11 (логирование), раздел 3 (_openai namespace)
- `docs/Thing' Sandbox LLM Usage Tracking.md` — правила учёта токенов
- Схемы: `src/schemas/Master.schema.json`, `src/schemas/NarrativeResponse.schema.json`
- Промпты: `src/prompts/phase2a_*.md`, `src/prompts/phase2b_*.md`

## Context

Phase 1 (намерения) и Phase 3 (применение результатов) реализованы. Промпты для Phase 2 разработаны. Спецификации Phase 2a и 2b написаны.

Нужно реализовать:
- **Phase 2a (арбитр)** — разрешение сцены в каждой локации
- **Phase 2b (нарратив)** — генерация человекочитаемого текста

Обе фазы работают per-location (в отличие от Phase 1, которая per-character).

### Entity Key Format

- Phase 2a: `"resolution:{location_id}"`
- Phase 2b: `"narrative:{location_id}"`

### Logging Emojis

- Phase 2a: ⚖️
- Phase 2b: 📖

---

## Steps

### 1. Реализовать `src/phases/phase2a.py`

Заменить stub на полную реализацию по спецификации `docs/specs/phase_2a.md`.

**Сигнатура execute:**
```python
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
    intentions: dict[str, str],  # char_id → intention string
) -> PhaseResult:
```

**Pydantic модели** (уже есть в стабе, добавить валидацию):
- `CharacterUpdate` — добавить `Field(..., min_length=1)` для memory_entry
- `LocationUpdate` — без изменений
- `MasterOutput` — без изменений

**Алгоритм:**
1. Создать PromptRenderer с путём к симуляции
2. Сгруппировать персонажей по локациям
3. Для каждой локации:
   - Найти персонажей в этой локации
   - Собрать их намерения из `intentions`
   - Отрендерить system/user промпты
   - Создать LLMRequest с `entity_key="resolution:{loc_id}"`
4. Выполнить batch
5. Обработать результаты с fallback для ошибок
6. Вернуть `PhaseResult(success=True, data=results)`

**Fallback** (см. спецификацию):
```python
def _create_fallback(
    simulation: Simulation,
    loc_id: str,
    chars_here: dict[str, Character],
) -> MasterOutput:
    """Create fallback MasterOutput when LLM fails."""
    char_updates = {}
    for char_id, char in chars_here.items():
        char_updates[char_id] = CharacterUpdate(
            location=char.state.location,
            internal_state=char.state.internal_state or "",
            external_intent=char.state.external_intent or "",
            memory_entry="[No resolution — simulation continues]",
        )
    return MasterOutput(
        tick=simulation.current_tick,
        location_id=loc_id,
        characters=char_updates,
        location=LocationUpdate(moment=None, description=None),
    )
```

### 2. Реализовать `src/phases/phase2b.py`

Заменить stub на полную реализацию по спецификации `docs/specs/phase_2b.md`.

**Сигнатура execute:**
```python
async def execute(
    simulation: Simulation,
    config: Config,
    llm_client: LLMClient,
    master_results: dict[str, MasterOutput],
    intentions: dict[str, str],
) -> PhaseResult:
```

**Pydantic модель:**
```python
class NarrativeResponse(BaseModel):
    narrative: str = Field(..., min_length=1)
```

**Контекст для промпта** (см. `phase2b_narrative_user.md`):
- `location_before` — Location из simulation (до изменений)
- `characters_before` — персонажи в локации (до изменений)
- `master_result` — MasterOutput для этой локации
- `intentions` — dict намерений персонажей в этой локации

**Fallback:**
```python
NarrativeResponse(narrative="[Silence in the location]")
```

### 3. Обновить `src/phases/__init__.py`

Добавить экспорты:
- `NarrativeResponse` из phase2b
- `MasterOutput`, `CharacterUpdate`, `LocationUpdate` из phase2a (если нужно)

### 4. Обновить `src/runner.py`

**a) Изменить вызов Phase 2a** — передать `intentions`:

```python
# Extract intention strings from Phase 1 results
intentions_str = {
    char_id: intent_resp.intention 
    for char_id, intent_resp in result1.data.items()
}

loc_client_p2a = self._create_loc_llm_client(self._config.phase2a)
result2a = await execute_phase2a(simulation, self._config, loc_client_p2a, intentions_str)
```

**b) Изменить вызов Phase 2b** — передать `llm_client`, `master_results`, `intentions`:

```python
loc_client_p2b = self._create_loc_llm_client(self._config.phase2b)
result2b = await execute_phase2b(
    simulation, 
    self._config, 
    loc_client_p2b, 
    result2a.data,
    intentions_str,
)
```

**c) Убрать `# type: ignore[arg-type]`** для phase2b.

**d) Обновить логирование phase2b** — реальная статистика:

```python
stats = loc_client_p2b.get_last_batch_stats()
self._accumulate_tick_stats(stats)
logger.info(
    "📖 phase2b: Complete (%d locs, %s tokens, %s reasoning)",
    len(simulation.locations),
    f"{stats.total_tokens:,}",
    f"{stats.reasoning_tokens:,}",
)
```

**e) Обновить извлечение narratives** — теперь NarrativeResponse:

```python
self._narratives: dict[str, str] = {}
for loc_id, narrative_resp in result2b.data.items():
    self._narratives[loc_id] = narrative_resp.narrative
```

### 5. Обновить `tests/unit/test_runner.py`

Обновить моки:
- Phase 2a теперь принимает 4 параметра (+ `intentions`)
- Phase 2b теперь принимает 5 параметров (+ `llm_client`, `master_results`, `intentions`)

### 6. Написать тесты

**tests/unit/test_phase2a.py** (см. спецификацию, секция Test Coverage):
- Тесты Pydantic моделей
- Тесты context assembly
- Тесты batch execution
- Тесты fallback
- Тесты структуры результата

**tests/unit/test_phase2b.py** (см. спецификацию, секция Test Coverage):
- Тесты NarrativeResponse
- Тесты context assembly
- Тесты batch execution
- Тесты fallback
- Тесты структуры результата

**tests/integration/test_phase2_integration.py:**
- `test_phase2a_real_llm` — реальный LLM генерирует валидный MasterOutput
- `test_phase2b_real_llm` — реальный LLM генерирует нарратив
- `test_phase2_full_chain` — phase1 → phase2a → phase2b работают вместе

Markers: `@pytest.mark.integration`, `@pytest.mark.slow`

Skip condition: `OPENAI_API_KEY` not set

---

## Testing

```bash
# Активировать venv
source venv/bin/activate

# Проверка качества кода
ruff check src/phases/phase2a.py src/phases/phase2b.py src/runner.py
ruff format src/phases/phase2a.py src/phases/phase2b.py src/runner.py
mypy src/phases/phase2a.py src/phases/phase2b.py src/runner.py

# Unit тесты
pytest tests/unit/test_phase2a.py tests/unit/test_phase2b.py tests/unit/test_runner.py -v

# Integration тесты (требуют OPENAI_API_KEY)
pytest tests/integration/test_phase2_integration.py -v -m integration

# Полный прогон
pytest --tb=short
```

---

## Deliverables

**Модули:**
- [ ] `src/phases/phase2a.py` (заменить stub)
- [ ] `src/phases/phase2b.py` (заменить stub)
- [ ] `src/phases/__init__.py` (обновить экспорты)
- [ ] `src/runner.py` (обновить вызовы фаз)

**Тесты:**
- [ ] `tests/unit/test_phase2a.py`
- [ ] `tests/unit/test_phase2b.py`
- [ ] `tests/unit/test_runner.py` (обновить)
- [ ] `tests/integration/test_phase2_integration.py`

**Спецификации (обновить статус если нужно):**
- [ ] `docs/specs/phase_2a.md` — статус READY
- [ ] `docs/specs/phase_2b.md` — статус READY

**Отчёт:**
- [ ] `docs/tasks/TS-B.3b-PHASE2-001_REPORT.md`

---

## Notes

### Порядок выполнения в runner

```
Phase 1 → intentions (dict[str, IntentionResponse])
    ↓
Phase 2a (intentions) → master_results (dict[str, MasterOutput])
    ↓
Phase 2b (master_results, intentions) → narratives (dict[str, NarrativeResponse])
    ↓
Phase 3 (master_results) → applies changes
    ↓
Phase 4 → memory updates
```

### Phase 2b получает состояние ДО изменений

Phase 2b выполняется до Phase 3, поэтому `simulation` содержит состояние до применения решений арбитра. Это намеренно — нарратор описывает переход от "до" к "после".

### Совместимость с Phase 3

Phase 3 уже реализована и ожидает `dict[str, MasterOutput]`. Убедись что MasterOutput из phase2a совместим.
