# TS-A.5b-ADAPTER-002: Extend AdapterResponse with Debug Info

## References

**Обязательно изучить перед началом работы:**
- `docs/specs/util_llm_errors.md` — текущая спецификация типов данных
- `docs/specs/util_llm_adapter_openai.md` — текущая спецификация адаптера
- `docs/Thing' Sandbox OpenAI Responses API Reference.md` — структура ответа API (разделы 3, 5)

**Текущая реализация:**
- `src/utils/llm_adapters/base.py`
- `src/utils/llm_adapters/openai.py`
- `tests/unit/test_llm_adapter_openai.py`

---

## Context

Адаптер OpenAI работает корректно, но собирает только базовую информацию об использовании токенов. Для отладки и анализа поведения агентов нужно расширить сбор данных.

**Цель этапа:** Расширить `AdapterResponse` дополнительной информацией для дебага:
- `cached_tokens` — эффективность prompt caching
- `total_tokens` — общее количество токенов
- `model` — фактическая модель (может отличаться от запрошенной)
- `created_at` — timestamp ответа
- `service_tier` — уровень обслуживания (default/flex/priority)
- `reasoning_summary` — саммари рассуждений reasoning-моделей

**Ключевое решение:** Всегда собираем всю доступную информацию — данные уже в ответе API, парсинг бесплатный. Транспортный слой решит, что логировать.

---

## Steps

### 1. Обновить `src/utils/llm_adapters/base.py`

**Расширить `ResponseUsage`:**
```python
@dataclass
class ResponseUsage:
    """Token usage statistics from API response."""
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0
    cached_tokens: int = 0      # NEW: из input_tokens_details.cached_tokens
    total_tokens: int = 0       # NEW: из usage.total_tokens
```

**Добавить `ResponseDebugInfo`:**
```python
@dataclass 
class ResponseDebugInfo:
    """Debug information extracted from API response.
    
    Always populated — parsing is cheap, transport layer decides what to log.
    """
    model: str                              # Фактическая модель (может быть alias)
    created_at: int                         # Unix timestamp создания ответа
    service_tier: str | None = None         # "default" / "flex" / "priority" / None
    reasoning_summary: list[str] | None = None  # Саммари рассуждений (если есть)
```

**Обновить `AdapterResponse`:**
```python
@dataclass
class AdapterResponse(Generic[T]):
    """Container for successful API response."""
    response_id: str
    parsed: T
    usage: ResponseUsage
    debug: ResponseDebugInfo  # NEW: всегда создаётся
```

**Обновить экспорт в `__init__.py`:**
```python
from src.utils.llm_adapters.base import (
    AdapterResponse,
    ResponseDebugInfo,  # NEW
    ResponseUsage,
)
```

### 2. Обновить `src/utils/llm_adapters/openai.py`

В методе `_process_response` расширить извлечение данных:

**Извлечение usage (добавить после существующего кода):**
```python
# Existing
input_tokens = getattr(usage_obj, "input_tokens", 0)
output_tokens = getattr(usage_obj, "output_tokens", 0)

# Extract reasoning tokens from output_tokens_details
output_tokens_details = getattr(usage_obj, "output_tokens_details", None)
reasoning_tokens = 0
if output_tokens_details:
    reasoning_tokens = getattr(output_tokens_details, "reasoning_tokens", 0) or 0

# NEW: Extract cached_tokens from input_tokens_details
input_tokens_details = getattr(usage_obj, "input_tokens_details", None)
cached_tokens = 0
if input_tokens_details:
    cached_tokens = getattr(input_tokens_details, "cached_tokens", 0) or 0

# NEW: Extract total_tokens
total_tokens = getattr(usage_obj, "total_tokens", 0)

usage = ResponseUsage(
    input_tokens=input_tokens,
    output_tokens=output_tokens,
    reasoning_tokens=reasoning_tokens,
    cached_tokens=cached_tokens,      # NEW
    total_tokens=total_tokens,        # NEW
)
```

**Извлечение debug info (добавить новый блок):**
```python
# NEW: Extract debug info
model = getattr(response, "model", "")
created_at = getattr(response, "created_at", 0)
service_tier = getattr(response, "service_tier", None)

# NEW: Extract reasoning summary if present
reasoning_summary: list[str] | None = None
output = getattr(response, "output", [])
for item in output:
    if getattr(item, "type", None) == "reasoning":
        summaries = getattr(item, "summary", [])
        if summaries:
            reasoning_summary = [
                getattr(s, "text", "") 
                for s in summaries 
                if getattr(s, "type", None) == "summary_text"
            ]
        break  # Reasoning block is always first if present

debug = ResponseDebugInfo(
    model=model,
    created_at=created_at,
    service_tier=service_tier,
    reasoning_summary=reasoning_summary,
)
```

**Обновить return:**
```python
return AdapterResponse(
    response_id=response_id,
    parsed=output_parsed,
    usage=usage,
    debug=debug,  # NEW
)
```

**Обновить import в начале файла:**
```python
from src.utils.llm_adapters.base import AdapterResponse, ResponseDebugInfo, ResponseUsage
```

**Обновить логирование:**
```python
logger.debug(
    "Response received: id=%s, model=%s, input=%d, output=%d, reasoning=%d, cached=%d",
    response_id,
    model,
    input_tokens,
    output_tokens,
    reasoning_tokens,
    cached_tokens,
)
```

### 3. Обновить unit-тесты

Файл: `tests/unit/test_llm_adapter_openai.py`

**Обновить `create_mock_response` helper:**
```python
def create_mock_response(
    response_id: str = "resp_test123",
    status: str = "completed",
    output_parsed: BaseModel | None = None,
    content_type: str = "output_text",
    refusal: str | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
    reasoning_tokens: int = 0,
    cached_tokens: int = 0,           # NEW
    total_tokens: int | None = None,  # NEW: auto-calculate if not set
    model: str = "gpt-test-model",    # NEW
    created_at: int = 1700000000,     # NEW
    service_tier: str | None = "default",  # NEW
    reasoning_summary: list[str] | None = None,  # NEW
    incomplete_reason: str | None = None,
    error_message: str | None = None,
) -> MagicMock:
    """Create a mock OpenAI response object."""
    mock_response = MagicMock()
    mock_response.id = response_id
    mock_response.status = status
    mock_response.output_parsed = output_parsed
    mock_response.model = model                    # NEW
    mock_response.created_at = created_at          # NEW
    mock_response.service_tier = service_tier      # NEW

    # Create output list
    output_list = []
    
    # NEW: Add reasoning block if summary provided
    if reasoning_summary is not None:
        reasoning_mock = MagicMock()
        reasoning_mock.type = "reasoning"
        reasoning_mock.summary = [
            MagicMock(type="summary_text", text=text) 
            for text in reasoning_summary
        ]
        output_list.append(reasoning_mock)

    # Create content mock (message block)
    content_mock = MagicMock()
    content_mock.type = content_type
    if refusal:
        content_mock.refusal = refusal

    output_mock = MagicMock()
    output_mock.content = [content_mock]
    output_list.append(output_mock)
    
    mock_response.output = output_list

    # Create usage mock
    usage_mock = MagicMock()
    usage_mock.input_tokens = input_tokens
    usage_mock.output_tokens = output_tokens
    usage_mock.total_tokens = total_tokens if total_tokens is not None else (input_tokens + output_tokens)  # NEW

    # NEW: input_tokens_details
    input_details_mock = MagicMock()
    input_details_mock.cached_tokens = cached_tokens
    usage_mock.input_tokens_details = input_details_mock

    # output_tokens_details
    output_details_mock = MagicMock()
    output_details_mock.reasoning_tokens = reasoning_tokens
    usage_mock.output_tokens_details = output_details_mock

    mock_response.usage = usage_mock

    # Incomplete details
    if incomplete_reason:
        incomplete_mock = MagicMock()
        incomplete_mock.reason = incomplete_reason
        mock_response.incomplete_details = incomplete_mock

    # Error
    if error_message:
        error_mock = MagicMock()
        error_mock.message = error_message
        mock_response.error = error_mock

    return mock_response
```

**Добавить новые тесты в класс `TestOpenAIAdapterExecuteSuccess`:**

```python
@pytest.mark.asyncio
async def test_cached_tokens_extracted(self, phase_config: PhaseConfig) -> None:
    """Extracts cached_tokens from input_tokens_details."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
        adapter = OpenAIAdapter(phase_config)

        mock_response = create_mock_response(
            output_parsed=SimpleAnswer(answer="42"),
            input_tokens=1000,
            cached_tokens=800,  # 80% cache hit
        )

        adapter.client.responses.parse = AsyncMock(return_value=mock_response)

        response = await adapter.execute(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
        )

        assert response.usage.cached_tokens == 800

@pytest.mark.asyncio
async def test_total_tokens_extracted(self, phase_config: PhaseConfig) -> None:
    """Extracts total_tokens from usage."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
        adapter = OpenAIAdapter(phase_config)

        mock_response = create_mock_response(
            output_parsed=SimpleAnswer(answer="42"),
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        adapter.client.responses.parse = AsyncMock(return_value=mock_response)

        response = await adapter.execute(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
        )

        assert response.usage.total_tokens == 150

@pytest.mark.asyncio
async def test_debug_info_populated(self, phase_config: PhaseConfig) -> None:
    """Debug info is always populated."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
        adapter = OpenAIAdapter(phase_config)

        mock_response = create_mock_response(
            output_parsed=SimpleAnswer(answer="42"),
            model="gpt-4.1-mini-2025-04-14",
            created_at=1700000000,
            service_tier="default",
        )

        adapter.client.responses.parse = AsyncMock(return_value=mock_response)

        response = await adapter.execute(
            instructions="Test",
            input_data="Test",
            schema=SimpleAnswer,
        )

        assert response.debug.model == "gpt-4.1-mini-2025-04-14"
        assert response.debug.created_at == 1700000000
        assert response.debug.service_tier == "default"
        assert response.debug.reasoning_summary is None  # No reasoning

@pytest.mark.asyncio
async def test_reasoning_summary_extracted(self, reasoning_config: PhaseConfig) -> None:
    """Extracts reasoning summary for reasoning models."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-123"}):
        adapter = OpenAIAdapter(reasoning_config)

        mock_response = create_mock_response(
            output_parsed=SimpleAnswer(answer="42"),
            reasoning_summary=["Considering the math...", "The answer is 42."],
            reasoning_tokens=256,
        )

        adapter.client.responses.parse = AsyncMock(return_value=mock_response)

        response = await adapter.execute(
            instructions="Think step by step.",
            input_data="What is 6 * 7?",
            schema=SimpleAnswer,
        )

        assert response.debug.reasoning_summary is not None
        assert len(response.debug.reasoning_summary) == 2
        assert "Considering the math" in response.debug.reasoning_summary[0]
```

**Обновить существующий тест `test_successful_response`** — добавить проверку debug:
```python
# В конце теста добавить:
assert response.debug is not None
assert response.debug.model == "gpt-test-model"
```

### 4. Обновить спецификации

**`docs/specs/util_llm_errors.md`:**

В разделе "Data Types" обновить `ResponseUsage`:
```markdown
#### ResponseUsage

Token usage statistics from API response.

```python
@dataclass
class ResponseUsage:
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
```

- **input_tokens** — tokens in prompt
- **output_tokens** — tokens in response (excluding reasoning)
- **reasoning_tokens** — reasoning tokens (for reasoning models, 0 otherwise)
- **cached_tokens** — tokens served from prompt cache (0 if no caching)
- **total_tokens** — total token count (input + output)
```

Добавить новый раздел после `ResponseUsage`:
```markdown
#### ResponseDebugInfo

Debug information extracted from API response. Always populated.

```python
@dataclass 
class ResponseDebugInfo:
    model: str
    created_at: int
    service_tier: str | None = None
    reasoning_summary: list[str] | None = None
```

- **model** — actual model used (may differ from requested due to aliases)
- **created_at** — Unix timestamp of response creation
- **service_tier** — "default", "flex", "priority", or None
- **reasoning_summary** — list of reasoning step summaries (for reasoning models with summary enabled)
```

Обновить раздел `AdapterResponse`:
```markdown
#### AdapterResponse[T]

```python
@dataclass
class AdapterResponse(Generic[T]):
    response_id: str
    parsed: T
    usage: ResponseUsage
    debug: ResponseDebugInfo
```

- **debug** — always populated with available debug info
```

**`docs/specs/util_llm_adapter_openai.md`:**

В разделе "Response Processing" добавить извлечение новых полей.

---

## Testing

**Активировать venv перед запуском:**
```bash
source venv/bin/activate
```

**Проверки качества кода:**
```bash
ruff check src/utils/llm_adapters/
ruff format src/utils/llm_adapters/
mypy src/utils/llm_adapters/
```

**Unit-тесты:**
```bash
pytest tests/unit/test_llm_adapter_openai.py -v
```

**Интеграционные тесты (опционально, для проверки реальных данных):**
```bash
pytest tests/integration/test_llm_adapter_openai_live.py -v -k "simple"
```

---

## Expected Results

### Проверки качества
- `ruff check` — 0 ошибок
- `ruff format` — файлы отформатированы
- `mypy` — 0 ошибок

### Unit-тесты
- Все существующие тесты проходят (обратная совместимость)
- Новые тесты на `cached_tokens`, `total_tokens`, `debug` проходят
- Тест на `reasoning_summary` проходит

### Пример работы
```python
response = await adapter.execute(...)

# Usage с расширенными полями
print(f"Input: {response.usage.input_tokens}")
print(f"Cached: {response.usage.cached_tokens}")  # NEW
print(f"Total: {response.usage.total_tokens}")    # NEW

# Debug info
print(f"Model: {response.debug.model}")           # NEW
print(f"Created: {response.debug.created_at}")    # NEW
print(f"Tier: {response.debug.service_tier}")     # NEW
if response.debug.reasoning_summary:              # NEW
    print(f"Reasoning: {response.debug.reasoning_summary}")
```

---

## Deliverables

1. **Обновлённые модули:**
   - `src/utils/llm_adapters/base.py` — новые поля в dataclasses
   - `src/utils/llm_adapters/openai.py` — расширенный парсинг
   - `src/utils/llm_adapters/__init__.py` — экспорт `ResponseDebugInfo`

2. **Обновлённые тесты:**
   - `tests/unit/test_llm_adapter_openai.py` — новые тесты + обновлённый helper

3. **Обновлённые спецификации:**
   - `docs/specs/util_llm_errors.md`
   - `docs/specs/util_llm_adapter_openai.md`

4. **Отчёт:** `docs/tasks/TS-A.5b-ADAPTER-002_REPORT.md`

---

## Notes

- Это рефакторинг без breaking changes — все существующие тесты должны пройти
- `debug` всегда создаётся, даже если какие-то поля None/пустые
- Reasoning summary доступен только если в запросе `reasoning.summary` ≠ null
- Для обычных моделей `reasoning_summary` будет None
