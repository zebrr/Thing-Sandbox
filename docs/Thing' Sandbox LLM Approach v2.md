# Thing' Sandbox: LLM Approach v2

Концептуальный документ по работе с LLM в проекте. Описывает архитектуру, async execution, управление chains и TPM.

**Заменяет:** `Thing' Sandbox LLM Approach.md` (сохраняем как референс)

---

## 1. Обзор и отличия от v1

| Аспект | v1 | v2 |
|--------|----|----|
| Execution model | Sync + background=True + polling | Async + background=False |
| Client state | Stateful (как k2-18) | Stateless фасад + ChainManager внутри |
| Interface | response_id возвращается наружу | Только Pydantic модель наружу |
| Confirmation | Two-phase (explicit confirm) | Auto-confirm |
| TPM estimation | Probe hack (background не возвращает headers) | Headers из sync response (MVP) или pre-flight `/v1/responses/input_tokens` |
| Chain storage | В памяти | В сущностях с namespace `_openai` |

**Почему async:**
- `background=False` возвращает rate limit headers — не нужен probe hack
- `asyncio.gather()` — готовый batch execution из коробки
- Меньше API вызовов (нет polling overhead)
- Код компактнее, логика яснее

---

## 2. Архитектура: слои и ответственности

```
┌─────────────────────────────────────────────────────────────┐
│                         Phases                              │
│  phase1.py, phase2a.py, phase2b.py, phase4.py               │
│                                                             │
│  Знают: промпты, схемы ответов, бизнес-логику, fallback     │
│  НЕ знают: OpenAI, response_id, chains, TPM, retry          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      LLMClient                              │
│  src/utils/llm.py                                           │
│                                                             │
│  Публичный интерфейс:                                       │
│  - create_response(instructions, input, schema, entity_key) │
│  - create_batch(requests) → list[Result]                    │
│                                                             │
│  Внутри: ChainManager, usage accumulation, выбор адаптера   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    OpenAIAdapter                            │
│  src/utils/llm_adapters/openai.py                           │
│                                                             │
│  Знает: OpenAI API, AsyncOpenAI, Structured Outputs         │
│  - execute(request) → AdapterResponse[T]                    │
│  - delete_response(response_id)                             │
│  Внутри: retry logic, timeout handling                      │
└─────────────────────────────────────────────────────────────┘
```

**Строгое правило:** Runner и фазы не импортируют ничего из `openai`. Только `LLMClient`, `LLMError`, Pydantic схемы.

**Разделение ответственности:**
- **Транспорт (Adapter):** retry, timeout, rate limit handling — молча
- **Клиент (LLMClient):** chains, usage accumulation, batch orchestration
- **Фазы:** fallback при ошибках (graceful degradation)

---

## 3. LLMClient — публичный интерфейс

```python
from pydantic import BaseModel
from typing import TypeVar

T = TypeVar("T", bound=BaseModel)

class LLMClient:
    """
    Провайдер-агностичный фасад для LLM запросов.
    Создаётся per-phase с соответствующим adapter и entities.
    """
    
    def __init__(
        self,
        adapter: OpenAIAdapter,
        entities: list[dict],
        default_depth: int = 0,
    ):
        """
        Args:
            adapter: Адаптер для LLM провайдера (OpenAI, etc.)
            entities: Список персонажей или локаций (мутируются in-place)
            default_depth: Глубина chain по умолчанию (из PhaseConfig)
        """
        self.adapter = adapter
        self.chain_manager = ResponseChainManager(entities)
        self.default_depth = default_depth
    
    async def create_response(
        self,
        instructions: str,
        input_data: str,
        schema: type[T],
        entity_key: str | None = None
    ) -> T:
        """
        Единичный запрос к LLM.
        
        Args:
            instructions: Системный промпт
            input_data: Пользовательские данные (контекст персонажа/локации)
            schema: Pydantic модель для Structured Output
            entity_key: Ключ для response chain ("intention:bob", "memory:elvira")
                       None = независимый запрос без chain
        
        Returns:
            Экземпляр schema с распарсенным ответом
        
        Raises:
            LLMRefusalError: Модель отказала по safety
            LLMIncompleteError: Ответ обрезан (max_tokens)
            LLMRateLimitError: Rate limit после всех retry
            LLMTimeoutError: Timeout после всех retry
            LLMError: Прочие ошибки
        """
        ...
    
    async def create_batch(
        self,
        requests: list[LLMRequest]
    ) -> list[T | LLMError]:
        """
        Batch запросов параллельно.
        
        Args:
            requests: Список запросов с instructions, input_data, schema, entity_key
        
        Returns:
            Список результатов в том же порядке.
            Успешные — экземпляры schema.
            Неуспешные — LLMError (не выбрасывается, возвращается в списке).
            
        Note:
            Retry выполняется внутри для каждого запроса молча.
            LLMError в результате означает, что все попытки исчерпаны.
        """
        ...


@dataclass
class LLMRequest:
    """Запрос для batch execution."""
    instructions: str
    input_data: str
    schema: type[BaseModel]
    entity_key: str | None = None
    depth_override: int | None = None  # Override default chain depth for this request
```

**Что НЕ протекает наружу:**
- `response_id`, `previous_response_id`
- `background`, `polling`
- TPM, headers, retry logic
- Любые OpenAI-специфичные типы

---

## 4. OpenAIAdapter — транспортный слой

**Ключевое решение:** используем `responses.parse()` вместо `responses.create()`. Это SDK helper который:
- Принимает Pydantic класс напрямую (не нужно конвертировать в JSON Schema)
- Возвращает уже распарсенный объект в `response.output_parsed`
- Упрощает код, убирает ручной JSON parse

```python
import os
import asyncio
import logging
from typing import TypeVar

import httpx
from openai import AsyncOpenAI, RateLimitError, APITimeoutError
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class OpenAIAdapter:
    """
    Адаптер для OpenAI Responses API.
    Знает всё про OpenAI, не виден снаружи LLMClient.
    """
    
    def __init__(self, config: PhaseConfig):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise LLMError("OPENAI_API_KEY environment variable not set")
        
        timeout = httpx.Timeout(float(config.timeout), connect=10.0)
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.config = config
    
    async def execute(
        self,
        instructions: str,
        input_data: str,
        schema: type[T],  # Pydantic класс, не dict!
        previous_response_id: str | None = None
    ) -> AdapterResponse[T]:
        """
        Выполнить запрос к OpenAI с retry.
        
        Retry выполняется молча для rate limit и timeout.
        
        Returns:
            AdapterResponse[T] с response_id, parsed (Pydantic модель), usage
            
        Raises:
            LLMRateLimitError: Rate limit после всех retry
            LLMTimeoutError: Timeout после всех retry
            LLMIncompleteError: Ответ обрезан
            LLMRefusalError: Модель отказала
            LLMError: Прочие ошибки
        """
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self._do_request(
                    instructions, input_data, schema, previous_response_id
                )
                return self._process_response(response)
            
            # Rate limit: ждём по header, retry
            except RateLimitError as e:
                if attempt >= self.config.max_retries:
                    raise LLMRateLimitError(f"Rate limit after {attempt + 1} attempts")
                wait = self._parse_reset_ms(e.response.headers)
                logger.warning(f"Rate limit hit, waiting {wait}s (attempt {attempt + 1})")
                await asyncio.sleep(wait)
            
            # Timeout: обрабатываем и httpx, и SDK exception
            except (httpx.TimeoutException, APITimeoutError) as e:
                if attempt >= self.config.max_retries:
                    raise LLMTimeoutError(f"Timeout after {attempt + 1} attempts")
                logger.warning(f"Timeout, retrying (attempt {attempt + 1})")
                await asyncio.sleep(1.0)
            
            # Refusal/Incomplete: не retry, сразу пробрасываем
            except (LLMRefusalError, LLMIncompleteError):
                raise
    
    async def _do_request(self, instructions, input_data, schema, previous_response_id):
        """Выполнить один запрос к OpenAI."""
        params = {
            "model": self.config.model,
            "instructions": instructions,
            "input": input_data,
            "text_format": schema,  # Pydantic класс напрямую!
            "max_output_tokens": self.config.max_completion,
            "store": True,
        }
        
        if previous_response_id:
            params["previous_response_id"] = previous_response_id
        
        # Reasoning параметры только если is_reasoning=True
        if self.config.is_reasoning:
            reasoning = {}
            if self.config.reasoning_effort:
                reasoning["effort"] = self.config.reasoning_effort
            if self.config.reasoning_summary:
                reasoning["summary"] = self.config.reasoning_summary
            if reasoning:
                params["reasoning"] = reasoning
        
        # Optional параметры только если заданы
        if self.config.truncation:
            params["truncation"] = self.config.truncation
        if self.config.verbosity:
            params["verbosity"] = self.config.verbosity
        
        return await self.client.responses.parse(**params)
    
    def _process_response(self, response) -> AdapterResponse[T]:
        """Обработать ответ OpenAI, выбросить ошибки если нужно."""
        # Проверка статуса
        if response.status == "incomplete":
            reason = response.incomplete_details.reason
            raise LLMIncompleteError(reason)
        
        if response.status == "failed":
            raise LLMError(f"Request failed: {response.error.message}")
        
        # Проверка refusal через content type
        content = response.output[0].content[0]
        if content.type == "refusal":
            raise LLMRefusalError(content.refusal)
        
        # Извлечение usage
        usage = ResponseUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            reasoning_tokens=response.usage.output_tokens_details.reasoning_tokens or 0,
        )
        
        # SDK уже распарсил в Pydantic модель!
        return AdapterResponse(
            response_id=response.id,
            parsed=response.output_parsed,  # уже T, не dict
            usage=usage,
        )
    
    def _parse_reset_ms(self, headers: httpx.Headers) -> float:
        """Парсинг времени ожидания из rate limit headers."""
        reset_str = headers.get("x-ratelimit-reset-tokens", "1000ms")
        try:
            if reset_str.endswith("ms"):
                return int(reset_str.rstrip("ms")) / 1000 + 0.5
            elif reset_str.endswith("s"):
                return float(reset_str.rstrip("s")) + 0.5
            else:
                return int(reset_str) / 1000 + 0.5
        except (ValueError, TypeError):
            return 1.5  # fallback
    
    async def delete_response(self, response_id: str) -> bool:
        """
        Удалить response из chain.
        
        Returns:
            True если удалено, False если ошибка (логируется, не выбрасывается)
        """
        try:
            await self.client.responses.delete(response_id)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete response {response_id}: {e}")
            return False


@dataclass
class AdapterResponse(Generic[T]):
    """Generic контейнер для ответа адаптера."""
    response_id: str
    parsed: T  # уже Pydantic модель, не dict!
    usage: ResponseUsage


@dataclass
class ResponseUsage:
    """Token usage статистика."""
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0
```

---

## 5. Async Batch Execution

```python
# Внутри LLMClient

async def create_batch(self, requests: list[LLMRequest]) -> list[T | LLMError]:
    self.rate_limit_hits = 0  # счётчик для диагностики
    
    # Параллельный запуск всех запросов (retry внутри adapter.execute)
    tasks = [self._execute_one(r) for r in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Логируем если были rate limit hits
    if self.rate_limit_hits > 0:
        logger.warning(f"Batch completed with {self.rate_limit_hits} rate limit hits")
        print(f"⚠️  Batch had {self.rate_limit_hits} rate limit hits — consider reviewing load")
    
    # Преобразуем результаты
    return [
        self._process_result(r, res) 
        for r, res in zip(requests, results)
    ]

async def _execute_one(self, request: LLMRequest) -> AdapterResponse:
    """
    Выполнить один запрос с учётом chain и usage tracking.
    
    Retry выполняется внутри adapter.execute() молча.
    """
    
    # Получить previous_response_id из chain (если есть)
    previous_id = None
    if request.entity_key:
        previous_id = self.chain_manager.get_previous(request.entity_key)
    
    # Конвертировать Pydantic schema → JSON Schema
    json_schema = self._to_json_schema(request.schema)
    
    # Выполнить запрос (retry внутри адаптера)
    response = await self.adapter.execute(
        instructions=request.instructions,
        input_data=request.input_data,
        schema=json_schema,
        previous_response_id=previous_id
    )
    
    # Auto-confirm: добавить в chain с нужным depth
    if request.entity_key:
        depth = request.depth_override if request.depth_override is not None else self.default_depth
        evicted = self.chain_manager.confirm(request.entity_key, response.response_id, depth)
        if evicted:
            # Ошибка deletion не критична — на след. такте удалится
            await self.adapter.delete_response(evicted)
    
    # Накопить usage для entity
    if request.entity_key:
        self._accumulate_usage(request.entity_key, response.usage)
    
    return response

def _accumulate_usage(self, entity_key: str, usage: ResponseUsage) -> None:
    """Накопить usage статистику в entity."""
    entity_id, _ = self.chain_manager._parse_key(entity_key)
    entity = self.chain_manager.entities.get(entity_id)
    if not entity:
        return
    
    if "_openai" not in entity:
        entity["_openai"] = {}
    
    if "usage" not in entity["_openai"]:
        entity["_openai"]["usage"] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_requests": 0
        }
    
    stats = entity["_openai"]["usage"]
    stats["total_input_tokens"] += usage.input_tokens
    stats["total_output_tokens"] += usage.output_tokens
    stats["total_requests"] += 1
```

---

## 6. TPM контроль

**MVP подход: Reactive**

При лимитах 1-2M TPM и типичном такте ~250K токенов, мы вряд ли упрёмся в лимиты. Поэтому:

- **Без TPMBucket** — не отслеживаем remaining заранее
- **Reactive retry** — если rate limit, ждём и повторяем (внутри адаптера)
- **Явное логирование** — чтобы быстро узнать если столкнёмся

**После batch'а / такта:**

```python
if self.rate_limit_hits > 0:
    logger.warning(f"Batch completed with {self.rate_limit_hits} rate limit hits")
    print(f"⚠️  Batch had {self.rate_limit_hits} rate limit hits — consider reviewing load")
```

**Когда усложнять:**

Если в логах начнут появляться `TPM LIMIT HIT` — тогда добавим:
- Pre-flight через `/v1/responses/input_tokens` (endpoint существует)
- TPMBucket с отслеживанием remaining
- Chunking больших batch'ей

Пока — YAGNI.

---

## 7. Response Chains

**ChainManager** — stateless helper для работы с chains в entities. Depth передаётся при `confirm()`, что позволяет разный depth для разных фаз и даже разных entities.

```python
class ResponseChainManager:
    """
    Stateless helper для работы с response chains в entities.
    
    Позволяет модели "помнить" предыдущие ответы через OpenAI
    previous_response_id. Depth передаётся при confirm() —
    это позволяет разный depth для разных фаз и даже разных entities.
    
    Работает с entities in-place: при confirm() мутирует
    entity["_openai"] напрямую. Storage сохраняет в конце такта.
    """
    
    def __init__(self, entities: list[dict]):
        """
        Args:
            entities: Список персонажей или локаций (мутируются in-place).
                     Каждый entity должен иметь identity.id.
        """
        self.entities: dict[str, dict] = {}
        for entity in entities:
            entity_id = entity.get("identity", {}).get("id", "")
            if entity_id:
                self.entities[entity_id] = entity
    
    def get_previous(self, entity_key: str) -> str | None:
        """
        Получить последний response_id из chain для entity.
        
        Args:
            entity_key: Ключ вида "intention:bob", "memory:elvira"
        
        Returns:
            response_id или None если chain пуст
        """
        entity_id, chain_name = self._parse_key(entity_key)
        entity = self.entities.get(entity_id)
        if not entity:
            return None
        
        chain_key = f"{chain_name}_chain"
        chain = entity.get("_openai", {}).get(chain_key, [])
        return chain[-1] if chain else None
    
    def confirm(
        self,
        entity_key: str,
        response_id: str,
        depth: int,
    ) -> str | None:
        """
        Добавить response в chain (мутирует entity in-place).
        
        Args:
            entity_key: Ключ вида "intention:bob", "memory:elvira"
            response_id: ID ответа от OpenAI
            depth: Глубина chain (0 = не добавлять, >0 = sliding window)
        
        Returns:
            Вытесненный response_id (для удаления) или None
        """
        if depth == 0:
            return None
        
        entity_id, chain_name = self._parse_key(entity_key)
        entity = self.entities.get(entity_id)
        if not entity:
            return None
        
        # Ensure _openai section exists
        if "_openai" not in entity:
            entity["_openai"] = {}
        
        chain_key = f"{chain_name}_chain"
        if chain_key not in entity["_openai"]:
            entity["_openai"][chain_key] = []
        
        chain = entity["_openai"][chain_key]
        
        # Sliding window: вытесняем старые если превышен depth
        evicted = None
        if len(chain) >= depth:
            evicted = chain.pop(0)
        
        chain.append(response_id)
        return evicted
    
    def _parse_key(self, entity_key: str) -> tuple[str, str]:
        """
        Парсинг entity_key в (entity_id, chain_name).
        
        "intention:bob" → ("bob", "intention")
        "memory:elvira" → ("elvira", "memory")
        """
        chain_name, entity_id = entity_key.split(":", 1)
        return entity_id, chain_name
```

**Auto-confirm:** если `adapter.execute()` вернул результат без exception — chain обновляется автоматически с depth из request или default. При refusal, incomplete — chain не трогаем.

---

## 8. Хранение состояния

Chains и usage хранятся в сущностях с namespace `_openai`:

```json
// characters/bob.json
{
  "identity": {...},
  "state": {...},
  "memory": {...},
  "_openai": {
    "intention_chain": ["resp_abc123", "resp_def456"],
    "memory_chain": ["resp_xyz789"],
    "usage": {
      "total_input_tokens": 125000,
      "total_output_tokens": 8500,
      "total_requests": 42
    }
  }
}
```

```json
// locations/tavern.json
{
  "identity": {...},
  "state": {...},
  "_openai": {
    "resolution_chain": ["resp_111"],
    "narrative_chain": ["resp_222"],
    "usage": {
      "total_input_tokens": 340000,
      "total_output_tokens": 45000,
      "total_requests": 84
    }
  }
}
```

```json
// simulation.json — агрегат по всей симуляции
{
  "id": "sim-01",
  "current_tick": 42,
  "status": "paused",
  "_openai": {
    "total_input_tokens": 1250000,
    "total_output_tokens": 180000,
    "total_requests": 420
  }
}
```

**Преимущества:**
- Всё в одном файле — удобно для debug
- Меньше I/O операций
- Multi-provider ready: `_anthropic`, `_openrouter` не конфликтуют
- Usage per entity — можно анализировать "дорогих" персонажей/локаций

**При depth=0:** секция chains не создаётся, но usage всё равно накапливается.

**Persistence:** ChainManager мутирует entities in-place. Runner загружает entities при старте симуляции, Storage сохраняет в конце каждого такта — chains и usage сохраняются автоматически.

---

## 9. Structured Outputs и Error Handling

**Structured Outputs** гарантируют валидный JSON по схеме. Two-phase confirmation не нужен — если ответ пришёл, он валиден.

**Иерархия ошибок:**

```python
class LLMError(Exception):
    """Базовый класс ошибок LLM."""
    pass

class LLMRefusalError(LLMError):
    """Модель отказала по safety reasons."""
    pass

class LLMIncompleteError(LLMError):
    """Ответ обрезан (достигнут max_output_tokens)."""
    pass

class LLMRateLimitError(LLMError):
    """Rate limit после всех retry."""
    pass

class LLMTimeoutError(LLMError):
    """Timeout после всех retry."""
    pass
```

**Retry в адаптере:** встроен для rate limit, timeout и transient errors. Выполняется молча. После исчерпания попыток — исключение.

**В batch:** исключения ловятся через `asyncio.gather(..., return_exceptions=True)`, возвращаются в списке результатов. Фаза использует fallback.

---

## 10. Graceful Degradation

Симуляция должна продолжаться даже при частичных сбоях LLM.

**Разделение ответственности:**
- **Транспорт (Adapter):** retry молча, timeout/rate limit handling
- **Клиент (LLMClient):** возвращает `LLMError` в списке batch результатов
- **Фазы:** реализуют fallback-стратегии

**Fallback по фазам:**

| Фаза | Что упало | Fallback | Эффект |
|------|-----------|----------|--------|
| **Phase 1** | Намерение персонажа | `intention: "idle"` | Персонаж бездействует один такт |
| **Phase 2a** | Арбитр локации | `MasterResponse.empty_fallback()` | Ничего не происходит в локации |
| **Phase 2b** | Нарратив локации | `"[Тишина в локации]"` | Лог будет скучный |
| **Phase 4** | Память персонажа | Оставить старую память | Память не обновилась |

**Пример обработки в фазе:**

```python
# Phase 1
async def process_intentions(characters: list, llm: LLMClient) -> list[Intention]:
    requests = [build_intention_request(c) for c in characters]
    results = await llm.create_batch(requests)
    
    intentions = []
    for char, result in zip(characters, results):
        if isinstance(result, LLMError):
            logger.warning(f"Phase 1 failed for {char.id}: {result}, using idle fallback")
            intentions.append(Intention(character_id=char.id, action="idle"))
        else:
            intentions.append(result)
    
    return intentions
```

**Логирование:** все fallback'и логируются как WARNING. Систематические fallback'и — сигнал разбираться с причиной.

---

## 11. Конфигурация

Каждая фаза с LLM имеет свою секцию конфига. Все параметры на уровне фазы — разные модели могут иметь разные лимиты.

```toml
# config.toml

[phase1]
model                   = "gpt-5-mini-2025-08-07"
is_reasoning            = true
max_context_tokens      = 400000
max_completion          = 128000
timeout                 = 600              # секунды, передаётся в httpx
max_retries             = 3
reasoning_effort        = "medium"
reasoning_summary       = "auto"
# verbosity             = "medium"         # Закомментирован = null (не передаётся)
truncation              = "auto"           # "auto" | "disabled" | закомментировано = не передается
response_chain_depth    = 0                # 0 = независимые запросы

[phase2a]
model                   = "gpt-5.1-2025-11-13"
is_reasoning            = true
max_context_tokens      = 400000
max_completion          = 128000
timeout                 = 600
max_retries             = 3
reasoning_effort        = "medium"
reasoning_summary       = "auto"
# verbosity             = "medium"
truncation              = "auto"
response_chain_depth    = 2                # Глубина цепочки

[phase2b]
model                   = "gpt-5-mini-2025-08-07"
is_reasoning            = true
max_context_tokens      = 400000
max_completion          = 128000
timeout                 = 600
max_retries             = 3
reasoning_effort        = "medium"
reasoning_summary       = "auto"
# verbosity             = "medium"
truncation              = "auto"
response_chain_depth    = 0

[phase4]
model                   = "gpt-5-mini-2025-08-07"
is_reasoning            = true
max_context_tokens      = 400000
max_completion          = 128000
timeout                 = 600
max_retries             = 3
reasoning_effort        = "medium"
reasoning_summary       = "auto"
# verbosity             = "medium"
truncation              = "auto"
response_chain_depth    = 0
```

**Pydantic модель в config.py:**

```python
class PhaseConfig(BaseModel):
    model: str
    is_reasoning: bool = False
    max_context_tokens: int = 128000
    max_completion: int = 4096
    timeout: int = 600                    # секунды
    max_retries: int = 3
    reasoning_effort: str | None = None
    reasoning_summary: str | None = None
    verbosity: str | None = None
    truncation: str | None = None
    response_chain_depth: int = 0
```

---

## 12. Переиспользование из k2-18

**Берём с адаптацией:**

| Компонент | Изменения |
|-----------|-----------|
| ResponseUsage | Без изменений |
| Паттерны тестов | MockResponse, helpers |

**Не берём:**
- TPMBucket (в MVP используем reactive подход)
- Stateful client логику
- Two-phase confirmation
- Background + polling
- Terminal output формат

---

## 13. Структура файлов

```
src/utils/
├── llm.py                    # LLMClient, LLMRequest, ChainManager
├── llm_errors.py             # LLMError hierarchy
├── llm_adapters/
│   ├── __init__.py           # Экспорт публичного API
│   ├── base.py               # AdapterResponse, ResponseUsage (типы данных)
│   │                         # TODO: BaseAdapter (абстракция) — когда появятся другие адаптеры
│   └── openai.py             # OpenAIAdapter
```

---

## Ссылки

- OpenAI Responses API: `docs/Thing' Sandbox OpenAI Responses API Reference.md`
- Structured Outputs: `docs/Thing' Sandbox OpenAI Structured model outputs API Reference.md`
- Предыдущая версия: `docs/Thing' Sandbox LLM Approach.md`
- k2-18 исходники: `C:\Users\Aski\Documents\AI\projects\semantic_graphs\k2-18\`
