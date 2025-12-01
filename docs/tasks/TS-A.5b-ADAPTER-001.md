# TS-A.5b-ADAPTER-001: Implement LLM Errors and OpenAI Adapter

## References

**Обязательно изучить перед началом работы:**
- `docs/specs/util_llm_errors.md` — спецификация типов данных и исключений
- `docs/specs/util_llm_adapter_openai.md` — спецификация OpenAI адаптера
- `docs/specs/core_config.md` — спецификация конфигурации (PhaseConfig)
- `docs/Thing' Sandbox LLM Approach v2.md` — концепция работы с LLM (разделы 2, 4, 9)

**Справочные материалы (при необходимости):**
- `docs/Thing' Sandbox OpenAI Responses API Reference.md`
- `docs/Thing' Sandbox OpenAI Structured model outputs API Reference.md`

---

## Context

Этап A.5a (PhaseConfig) завершён. Конфигурация фаз LLM загружается из `config.toml`.

**Цель этапа:** Реализовать транспортный слой для работы с OpenAI API:
- Общие типы данных (`AdapterResponse`, `ResponseUsage`)
- Иерархия исключений (`LLMError` и наследники)
- Адаптер `OpenAIAdapter` для OpenAI Responses API с Structured Outputs

**Ключевые особенности реализации:**
- Используем `responses.parse()` с `text_format=Pydantic` — SDK сам парсит ответ в Pydantic модель
- Retry выполняется молча внутри `execute()` для rate limit и timeout
- Refusal и incomplete — не retry, сразу exception
- `delete_response()` логирует ошибки, но не бросает исключения

---

## Steps

### 1. Создать структуру папок

```
src/utils/
├── llm_errors.py
└── llm_adapters/
    ├── __init__.py
    ├── base.py
    └── openai.py
```

### 2. Реализовать `src/utils/llm_errors.py`

Иерархия исключений (см. спеку `util_llm_errors.md`):

```python
class LLMError(Exception):
    """Base class for LLM-related errors."""
    pass

class LLMRefusalError(LLMError):
    """Model refused request due to safety policy."""
    def __init__(self, refusal_message: str):
        self.refusal_message = refusal_message
        super().__init__(f"Model refused: {refusal_message}")

class LLMIncompleteError(LLMError):
    """Response truncated due to token limit."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Response incomplete: {reason}")

class LLMRateLimitError(LLMError):
    """Rate limit exceeded after all retries."""
    pass

class LLMTimeoutError(LLMError):
    """Request timeout after all retries."""
    pass
```

### 3. Реализовать `src/utils/llm_adapters/base.py`

Общие типы данных (см. спеку `util_llm_errors.md`):

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass
class ResponseUsage:
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0

@dataclass
class AdapterResponse(Generic[T]):
    response_id: str
    parsed: T
    usage: ResponseUsage
```

### 4. Реализовать `src/utils/llm_adapters/__init__.py`

Экспорт публичного API:

```python
from src.utils.llm_adapters.base import AdapterResponse, ResponseUsage
from src.utils.llm_adapters.openai import OpenAIAdapter

__all__ = ["AdapterResponse", "ResponseUsage", "OpenAIAdapter"]
```

### 5. Реализовать `src/utils/llm_adapters/openai.py`

Основной адаптер (см. спеку `util_llm_adapter_openai.md`):

**Ключевые моменты:**

1. **Инициализация:**
   - Читать `OPENAI_API_KEY` из окружения
   - Создать `AsyncOpenAI` клиент с `httpx.Timeout(config.timeout, connect=10.0)`
   - Если ключ не задан — `LLMError`

2. **execute() метод:**
   - Принимает `instructions`, `input_data`, `schema` (Pydantic класс), `previous_response_id`
   - Вызывает `self.client.responses.parse()` с `text_format=schema`
   - Маппинг параметров: `config.max_completion` → API `max_output_tokens`
   - Reasoning параметры передавать только если `config.is_reasoning=True`
   - Optional параметры (`truncation`, `verbosity`) передавать только если не None

3. **Retry logic:**
   - Rate limit (RateLimitError от SDK): парсить `x-ratelimit-reset-tokens` из headers, ждать, retry
   - Timeout (httpx.TimeoutException): ждать 1 секунду, retry
   - После `max_retries` попыток — бросить `LLMRateLimitError` или `LLMTimeoutError`
   - Refusal и incomplete — НЕ retry, сразу exception

4. **Response processing:**
   - `status == "incomplete"` → `LLMIncompleteError(response.incomplete_details.reason)`
   - `status == "failed"` → `LLMError(response.error.message)`
   - `content.type == "refusal"` → `LLMRefusalError(content.refusal)`
   - Успех → `AdapterResponse(response_id, response.output_parsed, usage)`

5. **delete_response() метод:**
   - Вызвать `self.client.responses.delete(response_id)`
   - При ошибке — логировать warning, вернуть False
   - При успехе — вернуть True

**Важно про rate limit headers:**
Для получения headers нужно использовать `with_raw_response`:
```python
raw = await self.client.responses.with_raw_response.parse(...)
headers = raw.headers
response = raw.parse()
```

### 6. Написать unit-тесты

Файл: `tests/unit/test_llm_errors.py`
- Тесты иерархии исключений
- Тесты атрибутов (refusal_message, reason)
- Тесты ResponseUsage и AdapterResponse

Файл: `tests/unit/test_llm_adapter_openai.py`
- Mock `AsyncOpenAI` через `unittest.mock.AsyncMock`
- Тесты retry логики (rate limit, timeout)
- Тесты обработки статусов (completed, failed, incomplete)
- Тесты refusal (через mock!)
- Тесты delete_response

**Пример mock структуры для успешного ответа:**
```python
from unittest.mock import AsyncMock, MagicMock, patch

# Mock response object
mock_response = MagicMock()
mock_response.id = "resp_123"
mock_response.status = "completed"
mock_response.output_parsed = MySchema(field="value")
mock_response.output = [MagicMock(content=[MagicMock(type="output_text")])]
mock_response.usage = MagicMock(
    input_tokens=100,
    output_tokens=50,
    output_tokens_details=MagicMock(reasoning_tokens=0)
)
```

**Пример mock структуры для refusal (из документации Structured Outputs):**
```python
# Mock refusal response - тестируем через mock, не через реальный API!
# Структура ответа при refusal (из OpenAI Structured Outputs Reference):
mock_refusal_response = MagicMock()
mock_refusal_response.id = "resp_refusal_123"
mock_refusal_response.status = "completed"  # Статус completed, но content — refusal
mock_refusal_response.output_parsed = None  # При refusal parsed = None
mock_refusal_response.output = [MagicMock(
    content=[MagicMock(
        type="refusal",
        refusal="I'm sorry, I cannot assist with that request."
    )]
)]
mock_refusal_response.usage = MagicMock(
    input_tokens=81,
    output_tokens=11,
    output_tokens_details=MagicMock(reasoning_tokens=0)
)
```

### 7. Написать интеграционные тесты

Файл: `tests/integration/test_llm_adapter_openai_live.py`

**Конфигурация — брать из config.phase1:**
```python
import os
import pytest
from src.config import Config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]

@pytest.fixture
def integration_config():
    """Конфигурация для интеграционных тестов — берём из phase1"""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    
    config = Config.load()
    return config.phase1
```

**Тестовые Pydantic схемы:**
```python
from pydantic import BaseModel

class SimpleAnswer(BaseModel):
    answer: str

class MathStep(BaseModel):
    explanation: str
    output: str

class MathReasoning(BaseModel):
    steps: list[MathStep]
    final_answer: str
```

**Тесты (используй реальный API!):**

#### test_simple_structured_output
Базовый запрос со structured output:
```python
@pytest.mark.timeout(60)
async def test_simple_structured_output(integration_config):
    """Тест простого structured output запроса"""
    adapter = OpenAIAdapter(integration_config)
    
    response = await adapter.execute(
        instructions="Answer briefly.",
        input_data="What is 2+2? Answer with just the number.",
        schema=SimpleAnswer,
    )
    
    assert response.parsed is not None
    assert "4" in response.parsed.answer
    assert response.response_id.startswith("resp_")
    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0
```

#### test_complex_structured_output
Сложная схема (Math Tutor из референса):
```python
@pytest.mark.timeout(120)
async def test_complex_structured_output(integration_config):
    """Тест сложного structured output с вложенной схемой"""
    adapter = OpenAIAdapter(integration_config)
    
    response = await adapter.execute(
        instructions="You are a helpful math tutor. Guide the user through the solution step by step.",
        input_data="How can I solve 8x + 7 = -23?",
        schema=MathReasoning,
    )
    
    assert response.parsed is not None
    assert len(response.parsed.steps) > 0
    assert response.parsed.final_answer is not None
    # Проверяем что ответ содержит правильное решение: x = -30/8 = -15/4 = -3.75
    assert "-" in response.parsed.final_answer  # Ответ отрицательный
```

#### test_delete_response
```python
@pytest.mark.timeout(60)
async def test_delete_response(integration_config):
    """Тест удаления response"""
    adapter = OpenAIAdapter(integration_config)
    
    # Создаём response
    response = await adapter.execute(
        instructions="Answer briefly.",
        input_data="Say hello.",
        schema=SimpleAnswer,
    )
    response_id = response.response_id
    
    # Удаляем
    result = await adapter.delete_response(response_id)
    assert result is True
    
    # Проверяем что действительно удалён (через retrieve должен быть 404)
    # Это опционально — можно просто проверить что delete вернул True
```

#### test_incomplete_response (адаптировано из k2-18)
```python
@pytest.mark.timeout(120)
async def test_incomplete_response(integration_config):
    """Тест обработки incomplete ответа — недостаточно токенов для structured output"""
    from src.utils.llm_errors import LLMIncompleteError
    
    # Создаём конфиг с маленьким лимитом токенов
    # Копируем чтобы не мутировать оригинал
    limited_config = integration_config.model_copy()
    limited_config.max_completion = 300  # Мало для сложного ответа
    
    adapter = OpenAIAdapter(limited_config)
    
    with pytest.raises(LLMIncompleteError) as exc_info:
        await adapter.execute(
            instructions="You are a helpful math tutor. Solve with detailed step-by-step proof.",
            input_data=(
                "Prove that there are infinitely many prime numbers. "
                "Show complete formal proof with all steps explained in detail."
            ),
            schema=MathReasoning,
        )
    
    assert "incomplete" in str(exc_info.value).lower()
```

#### test_timeout (адаптировано из k2-18)
```python
@pytest.mark.timeout(30)  # Тест сам должен быть быстрым
async def test_timeout(integration_config):
    """Тест таймаута — короткий timeout + сложный промпт"""
    from src.utils.llm_errors import LLMTimeoutError
    
    # Создаём конфиг с коротким таймаутом
    timeout_config = integration_config.model_copy()
    timeout_config.timeout = 2  # 2 секунды — очень мало
    timeout_config.max_retries = 0  # Без retry для чистоты теста
    
    adapter = OpenAIAdapter(timeout_config)
    
    with pytest.raises(LLMTimeoutError) as exc_info:
        await adapter.execute(
            instructions="Think carefully step by step. Be extremely thorough.",
            input_data=(
                "Prove the Riemann hypothesis or explain in detail "
                "why it remains unproven. Include all mathematical background."
            ),
            schema=MathReasoning,
        )
    
    error_msg = str(exc_info.value)
    assert "timeout" in error_msg.lower() or "2" in error_msg
```

#### test_previous_response_id
```python
@pytest.mark.timeout(120)
async def test_previous_response_id(integration_config):
    """Тест что previous_response_id передаёт контекст"""
    adapter = OpenAIAdapter(integration_config)
    
    # Первый запрос
    response1 = await adapter.execute(
        instructions="Remember the user's name.",
        input_data="My name is Alice. What is 2+2?",
        schema=SimpleAnswer,
    )
    assert "4" in response1.parsed.answer
    
    # Второй запрос с previous_response_id
    response2 = await adapter.execute(
        instructions="Recall information from context.",
        input_data="What was my name?",
        schema=SimpleAnswer,
        previous_response_id=response1.response_id,
    )
    assert "alice" in response2.parsed.answer.lower()
    
    # Cleanup
    await adapter.delete_response(response1.response_id)
    await adapter.delete_response(response2.response_id)
```

#### test_reasoning_model (если is_reasoning=True)
```python
@pytest.mark.timeout(180)  # Reasoning модели медленнее
async def test_reasoning_model(integration_config):
    """Тест reasoning модели — должны быть reasoning_tokens"""
    if not integration_config.is_reasoning:
        pytest.skip("Test requires reasoning model (is_reasoning=True)")
    
    adapter = OpenAIAdapter(integration_config)
    
    response = await adapter.execute(
        instructions="Solve the math problem.",
        input_data="What is 123 * 456?",
        schema=SimpleAnswer,
    )
    
    assert response.parsed is not None
    # 123 * 456 = 56088
    assert "56088" in response.parsed.answer or "56,088" in response.parsed.answer
    # Reasoning модели должны использовать reasoning tokens
    assert response.usage.reasoning_tokens > 0
```

#### test_error_invalid_api_key
```python
@pytest.mark.timeout(30)
async def test_error_invalid_api_key(integration_config):
    """Тест ошибки при невалидном API ключе"""
    from src.utils.llm_errors import LLMError
    
    # Временно подменяем ключ
    import os
    original_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "sk-invalid-key-12345"
    
    try:
        # Создаём адаптер с невалидным ключом
        bad_config = integration_config.model_copy()
        bad_config.max_retries = 0
        adapter = OpenAIAdapter(bad_config)
        
        with pytest.raises(LLMError) as exc_info:
            await adapter.execute(
                instructions="Test",
                input_data="Test",
                schema=SimpleAnswer,
            )
        
        error_msg = str(exc_info.value).lower()
        assert "auth" in error_msg or "invalid" in error_msg or "api" in error_msg
    finally:
        # Восстанавливаем ключ
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
```

**Важно:** Refusal тестируется через mock в unit-тестах, НЕ через реальный API (ненадёжно).

---

## Testing

**Активировать venv перед запуском:**
```bash
# MacOS
source venv/bin/activate

# Windows  
.\venv\Scripts\activate
```

**Проверки качества кода:**
```bash
ruff check src/utils/llm_errors.py src/utils/llm_adapters/
ruff format src/utils/llm_errors.py src/utils/llm_adapters/
mypy src/utils/llm_errors.py src/utils/llm_adapters/
```

**Unit-тесты:**
```bash
pytest tests/unit/test_llm_errors.py -v
pytest tests/unit/test_llm_adapter_openai.py -v
```

**Интеграционные тесты (требуют OPENAI_API_KEY):**
```bash
pytest tests/integration/test_llm_adapter_openai_live.py -v
```

**Все тесты вместе:**
```bash
pytest tests/unit/test_llm_errors.py tests/unit/test_llm_adapter_openai.py tests/integration/test_llm_adapter_openai_live.py -v
```

---

## Expected Results

### Проверки качества
- `ruff check` — 0 ошибок
- `ruff format` — файлы отформатированы
- `mypy` — 0 ошибок

### Unit-тесты
- Все тесты проходят
- Покрытие основных сценариев: успех, retry, ошибки

### Интеграционные тесты
- Все тесты проходят с реальным API
- `test_refusal` подтверждает корректную обработку отказа
- `test_incomplete_response` подтверждает обработку обрезанного ответа

### Пример работы адаптера
```python
from pydantic import BaseModel
from src.utils.llm_adapters import OpenAIAdapter
from src.config import Config

class SimpleAnswer(BaseModel):
    answer: str

config = Config.load()
adapter = OpenAIAdapter(config.phase1)

response = await adapter.execute(
    instructions="Answer in one word.",
    input_data="What is 2+2?",
    schema=SimpleAnswer,
)

assert response.parsed.answer == "4"  # или "Four"
assert response.response_id.startswith("resp_")
assert response.usage.input_tokens > 0
```

---

## Deliverables

1. **Модули:**
   - `src/utils/llm_errors.py`
   - `src/utils/llm_adapters/__init__.py`
   - `src/utils/llm_adapters/base.py`
   - `src/utils/llm_adapters/openai.py`

2. **Тесты:**
   - `tests/unit/test_llm_errors.py`
   - `tests/unit/test_llm_adapter_openai.py`
   - `tests/integration/test_llm_adapter_openai_live.py`

3. **Спецификации:** обновить статус на `READY`
   - `docs/specs/util_llm_errors.md`
   - `docs/specs/util_llm_adapter_openai.md`

4. **Отчёт:** `docs/tasks/TS-A.5b-ADAPTER-001_REPORT.md`

---

## Notes

- API ключ уже настроен в `.env` — интеграционные тесты должны запускаться
- Для тестов используй недорогую модель (например, `gpt-5-mini-2025-08-07` или что указано в config.toml)
- Если столкнёшься с rate limit при тестах — это нормально, retry должен отработать
- Логирование через стандартный `logging` модуль
