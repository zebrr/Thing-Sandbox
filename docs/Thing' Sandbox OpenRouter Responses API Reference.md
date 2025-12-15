# OpenRouter Responses API Reference - Thing' Sandbox v1.0

Сокращённый референс OpenRouter Responses API для проекта Thing' Sandbox.
Основан на официальной документации OpenRouter.

**Источник:** https://openrouter.ai/docs/api/api-reference/responses/create-responses

---

## 1. CREATE Response Endpoint

### Endpoint

`POST https://openrouter.ai/api/v1/responses`

### Заголовки аутентификации

```bash
Authorization: Bearer OPENROUTER_API_KEY
Content-Type: application/json
```

### Request Body Parameters

#### Обязательные параметры

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | string | ID модели (например `anthropic/claude-4.5-sonnet`) |
| `input` | string/array | Входной контент — строка или массив input объектов |

#### Основные параметры

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `instructions` | string | null | Системные инструкции для модели |
| `temperature` | float | null | Управление случайностью (0.0 - 2.0) |
| `top_p` | float | null | Nucleus sampling параметр |
| `top_k` | float | — | Top-K sampling (OpenRouter-специфичный) |
| `max_output_tokens` | integer | null | Максимальное количество токенов для генерации |
| `previous_response_id` | string | null | ID предыдущего ответа для продолжения диалога |
| `store` | boolean | false | Сохранять ли запрос (только `false` в OpenRouter) |
| `metadata` | object | {} | Пользовательские метаданные |

#### Конфигурация Reasoning

```json
{
  "reasoning": {
    // Уровень усилий рассуждения
    // "none" - без reasoning (OpenRouter-специфичный)
    // "minimal" - минимум reasoning токенов
    // "low" - быстрые ответы с минимальными рассуждениями
    // "medium" - сбалансированная глубина (по умолчанию)
    // "high" - глубокие рассуждения
    // "xhigh" - максимальная глубина (OpenRouter-специфичный)
    "effort": "none|minimal|low|medium|high|xhigh",

    // Формат резюме рассуждений
    // "auto" - система выбирает формат автоматически
    // "concise" - краткое резюме
    // "detailed" - подробное резюме
    "summary": "auto|concise|detailed",

    // Максимум токенов на reasoning (опционально)
    "max_tokens": null,

    // Включить/выключить reasoning (опционально)
    "enabled": true
  }
}
```

**Отличие от OpenAI:** OpenRouter добавляет уровни `"none"` и `"xhigh"`.

#### Конфигурация Text Format (Structured Output)

```json
{
  "text": {
    "format": {
      "type": "json_schema",
      "name": "MyResponseSchema",
      "description": "Optional description",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "intention": { "type": "string" },
          "confidence": { "type": "number" }
        },
        "required": ["intention", "confidence"],
        "additionalProperties": false
      }
    },
    // Verbosity для GPT-5 серии (опционально)
    "verbosity": "low|medium|high"
  }
}
```

**Важно для Structured Output:**
- `type: "json_schema"` — включает structured output
- `strict: true` — гарантирует соответствие схеме
- `schema` — JSON Schema объект

Альтернативные форматы:
- `{ "type": "text" }` — обычный текстовый ответ
- `{ "type": "json_object" }` — JSON без схемы

#### Конфигурация Provider (OpenRouter-специфичный)

```json
{
  "provider": {
    // Разрешить fallback на другие провайдеры при ошибке
    "allow_fallbacks": true,

    // Порядок предпочтения провайдеров
    "order": ["OpenAI", "Anthropic", "Google"],

    // Использовать ТОЛЬКО эти провайдеры
    "only": ["OpenAI"],

    // Игнорировать эти провайдеры
    "ignore": ["Anthropic"],

    // Допустимые квантизации
    "quantizations": ["fp16", "int8"],

    // Сортировка провайдеров
    "sort": "price|throughput|latency",

    // Максимальная цена за токен
    "max_price": {
      "prompt": "0.001",
      "completion": "0.002"
    },

    // Zero Data Retention режим
    "zdr": true,

    // Data collection policy
    "data_collection": "deny|allow"
  }
}
```

#### Модели с Fallback

```json
{
  "model": "anthropic/claude-4.5-sonnet",
  "models": [
    "anthropic/claude-4.5-sonnet",
    "openai/gpt-4o",
    "google/gemini-pro"
  ],
  "route": "fallback"
}
```

- `models[]` — список моделей для fallback
- `route: "fallback"` — при ошибке пробовать следующую модель
- `route: "sort"` — выбирать лучшую по критериям

#### Дополнительные параметры

| Parameter | Type | Description |
|-----------|------|-------------|
| `truncation` | object | Стратегия обрезки контекста |
| `service_tier` | string | `"auto"` |
| `background` | boolean | Фоновое выполнение |
| `prompt_cache_key` | string | Ключ для кеширования промптов |
| `safety_identifier` | string | ID пользователя для safety |
| `include` | array | Дополнительные поля в ответе |
| `tools` | array | Function tools (не используем в проекте) |
| `tool_choice` | string | `"auto"`, `"none"`, `"required"` |

---

## 2. Input Object Structure

### Простой текстовый ввод

```json
{
  "input": "Describe the current situation."
}
```

### Массив сообщений

```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": "Hello, how are you?"
    }
  ]
}
```

### Message Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | No | `"message"` (можно опустить) |
| `role` | string | Yes | `"user"`, `"assistant"`, `"system"`, `"developer"` |
| `content` | string/array | Yes | Текст или массив content parts |

### Content Parts

#### Text Content

```json
{
  "type": "input_text",
  "text": "Your text here"
}
```

#### Image Content (если нужно)

```json
{
  "type": "input_image",
  "image_url": "https://example.com/image.png",
  "detail": "auto|high|low"
}
```

---

## 3. Response Object Structure

### Основной объект ответа

```json
{
  "id": "resp-abc123",
  "object": "response",
  "created_at": 1704067200,
  "model": "anthropic/claude-4.5-sonnet",
  "status": "completed|incomplete|in_progress|failed|cancelled|queued",

  "output": [
    // Массив output items
  ],

  "output_text": "Convenience field with final text",

  "error": {
    "code": "server_error|rate_limit_exceeded|invalid_prompt|...",
    "message": "Error description"
  },

  "incomplete_details": {
    "reason": "max_output_tokens|content_filter"
  },

  "usage": {
    "input_tokens": 100,
    "output_tokens": 50,
    "total_tokens": 150,
    "input_tokens_details": {
      "cached_tokens": 20
    },
    "output_tokens_details": {
      "reasoning_tokens": 30
    },
    // OpenRouter-специфичные поля
    "cost": 0.00025,
    "is_byok": false,
    "cost_details": {
      "upstream_inference_cost": 0.00020,
      "upstream_inference_input_cost": 0.00010,
      "upstream_inference_output_cost": 0.00010
    }
  },

  // Echo параметров запроса
  "temperature": 0.7,
  "top_p": 0.9,
  "max_output_tokens": 4096,
  "instructions": "...",
  "metadata": {},
  "previous_response_id": null,
  "reasoning": { "effort": "medium", "summary": "auto" },
  "service_tier": "default",
  "truncation": "auto|disabled",
  "text": { "format": {...} }
}
```

### Status Codes

| Status | Description |
|--------|-------------|
| `completed` | Генерация завершена успешно |
| `incomplete` | Ответ обрезан (см. `incomplete_details`) |
| `in_progress` | Генерация в процессе |
| `failed` | Ошибка (см. `error`) |
| `cancelled` | Отменено |
| `queued` | В очереди |

### Error Codes

| Code | Description |
|------|-------------|
| `server_error` | Внутренняя ошибка сервера |
| `rate_limit_exceeded` | Превышен rate limit |
| `invalid_prompt` | Невалидный промпт |
| `invalid_image` | Проблема с изображением |
| `image_content_policy_violation` | Нарушение политики контента |

### Incomplete Reasons

| Reason | Description |
|--------|-------------|
| `max_output_tokens` | Достигнут лимит токенов |
| `content_filter` | Сработал content filter |

---

## 4. Output Items

### Message Output (основной)

```json
{
  "id": "msg-abc123",
  "type": "message",
  "role": "assistant",
  "status": "completed|incomplete|in_progress",
  "content": [
    {
      "type": "output_text",
      "text": "Response text here",
      "annotations": []
    }
  ]
}
```

### Refusal Output

```json
{
  "type": "refusal",
  "refusal": "I cannot help with that request."
}
```

**Важно:** Refusal приходит внутри `content[]` массива message.

### Reasoning Output (для reasoning моделей)

```json
{
  "id": "rs-abc123",
  "type": "reasoning",
  "status": "completed",
  "content": [
    {
      "type": "reasoning_text",
      "text": "Let me think about this..."
    }
  ],
  "summary": [
    {
      "type": "summary_text",
      "text": "Brief summary of reasoning"
    }
  ],
  "encrypted_content": null,
  "signature": null,
  "format": "openai-responses-v1|anthropic-claude-v1|google-gemini-v1|xai-responses-v1"
}
```

**Порядок output items:**
- Обычные модели: `output[0]` = message
- Reasoning модели: `output[0]` = reasoning, `output[1]` = message

### Function Call Output (для tools)

```json
{
  "id": "fc-abc123",
  "type": "function_call",
  "name": "get_weather",
  "arguments": "{\"location\": \"Moscow\"}",
  "call_id": "call-xyz",
  "status": "completed"
}
```

---

## 5. Usage Object (детально)

```json
{
  "usage": {
    // Стандартные поля (как в OpenAI)
    "input_tokens": 1000,
    "output_tokens": 200,
    "total_tokens": 1200,

    "input_tokens_details": {
      "cached_tokens": 500  // Токены из кэша
    },

    "output_tokens_details": {
      "reasoning_tokens": 150  // Токены на reasoning
    },

    // OpenRouter-специфичные поля (бонус!)
    "cost": 0.00125,  // Общая стоимость в USD
    "is_byok": false,  // Bring Your Own Key

    "cost_details": {
      "upstream_inference_cost": 0.00100,
      "upstream_inference_input_cost": 0.00050,
      "upstream_inference_output_cost": 0.00050
    }
  }
}
```

**Преимущество OpenRouter:** Автоматический расчёт стоимости!

---

## 6. HTTP Status Codes

| Code | Description |
|------|-------------|
| `200` | Успешный ответ |
| `400` | Bad Request — невалидные параметры |
| `401` | Unauthorized — невалидный API key |
| `402` | Payment Required — недостаточно средств |
| `404` | Not Found — ресурс не найден |
| `408` | Request Timeout — превышено время ожидания |
| `413` | Payload Too Large — слишком большой запрос |
| `422` | Unprocessable Entity — семантическая ошибка |
| `429` | Too Many Requests — rate limit |
| `500` | Internal Server Error |
| `502` | Bad Gateway — ошибка провайдера |
| `503` | Service Unavailable |

---

## 7. Usage Examples

### Базовый запрос

```python
import requests

url = "https://openrouter.ai/api/v1/responses"

payload = {
    "model": "anthropic/claude-4.5-sonnet",
    "input": "Describe the current situation in the town square.",
    "instructions": "You are a narrative assistant for a text simulation.",
    "temperature": 0.7,
    "max_output_tokens": 4096
}

headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

### Запрос с Structured Output

```python
payload = {
    "model": "anthropic/claude-4.5-sonnet",
    "input": "What does Bob want to do?",
    "instructions": "Determine character intention.",
    "text": {
        "format": {
            "type": "json_schema",
            "name": "IntentionResponse",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "intention": {
                        "type": "string",
                        "description": "Character's intended action"
                    },
                    "target": {
                        "type": "string",
                        "description": "Target of the action"
                    }
                },
                "required": ["intention"],
                "additionalProperties": False
            }
        }
    },
    "max_output_tokens": 1000
}
```

### Запрос с Reasoning

```python
payload = {
    "model": "anthropic/claude-4.5-sonnet",
    "input": "Analyze the conflict between Bob and Alice...",
    "reasoning": {
        "effort": "medium",
        "summary": "concise"
    },
    "max_output_tokens": 25000
}
```

### Запрос с Response Chain

```python
# Первый запрос
response1 = requests.post(url, json={
    "model": "anthropic/claude-4.5-sonnet",
    "input": "Bob enters the tavern.",
    "instructions": "Remember this scene."
}, headers=headers)

response1_id = response1.json()["id"]

# Второй запрос с контекстом
response2 = requests.post(url, json={
    "model": "anthropic/claude-4.5-sonnet",
    "input": "What does Bob see?",
    "previous_response_id": response1_id
}, headers=headers)
```

### Запрос с Provider Routing

```python
payload = {
    "model": "anthropic/claude-4.5-sonnet",
    "models": [
        "anthropic/claude-4.5-sonnet",
        "openai/gpt-4o"
    ],
    "route": "fallback",
    "provider": {
        "allow_fallbacks": True,
        "data_collection": "deny"
    },
    "input": "Hello!"
}
```

---

## 8. Обработка ответа

### Извлечение текста

```python
response_data = response.json()

# Способ 1: convenience field
text = response_data.get("output_text")

# Способ 2: из output array
if response_data["status"] == "completed":
    for item in response_data["output"]:
        if item["type"] == "message":
            for content in item["content"]:
                if content["type"] == "output_text":
                    text = content["text"]
                elif content["type"] == "refusal":
                    refusal = content["refusal"]
```

### Проверка статуса

```python
def handle_response(response_data):
    status = response_data["status"]

    if status == "completed":
        return response_data["output_text"]

    elif status == "failed":
        error = response_data.get("error", {})
        raise Exception(f"Failed: {error.get('message')}")

    elif status == "incomplete":
        reason = response_data.get("incomplete_details", {}).get("reason")
        if reason == "max_output_tokens":
            # Можно retry с большим лимитом
            pass
        raise Exception(f"Incomplete: {reason}")

    else:
        raise Exception(f"Unexpected status: {status}")
```

### Извлечение Usage

```python
usage = response_data.get("usage", {})

input_tokens = usage.get("input_tokens", 0)
output_tokens = usage.get("output_tokens", 0)
total_tokens = usage.get("total_tokens", 0)

# Детали
cached = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
reasoning = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)

# OpenRouter бонус: стоимость
cost = usage.get("cost", 0)
```

### Проверка Refusal

```python
def check_refusal(response_data):
    for item in response_data.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "refusal":
                    return content.get("refusal")
    return None
```

---

## 9. Rate Limiting и Retry Logic

### Rate Limit Headers

При 429 ошибке OpenRouter возвращает headers в теле ответа (не в HTTP headers!):

```json
{
  "error": {
    "code": 429,
    "message": "Rate limit exceeded",
    "metadata": {
      "headers": {
        "X-RateLimit-Limit": "80",
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": "1741305600000"
      }
    }
  }
}
```

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Максимум запросов в окне |
| `X-RateLimit-Remaining` | Оставшиеся запросы |
| `X-RateLimit-Reset` | Unix timestamp в **миллисекундах** для reset |

**Важное отличие от OpenAI:** Headers приходят в `error.metadata.headers`, а не в HTTP response headers!

### Rate Limits по типам пользователей

| Тип пользователя | Лимиты |
|------------------|--------|
| **Free (без покупок)** | 50 запросов/день к free моделям |
| **Paid ($10+ credits)** | 1000 запросов/день к free моделям |
| **Free model variants (`:free`)** | 20 req/min, 200 req/day |
| **Pay-as-you-go / Enterprise** | Без platform-level лимитов |

### Проверка лимитов и баланса

```python
import requests

response = requests.get(
    url="https://openrouter.ai/api/v1/key",
    headers={"Authorization": "Bearer YOUR_API_KEY"}
)

data = response.json()
# {
#   "limit": 100.0,           # Credit ceiling (null if unlimited)
#   "limit_remaining": 50.0,  # Available credits
#   "usage": 50.0,            # Total consumed
#   "is_free_tier": false     # Has purchased credits
# }
```

### Retry Logic

```python
import time

def call_with_retry(payload, max_retries=3):
    for attempt in range(max_retries + 1):
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            error_data = response.json().get("error", {})
            metadata = error_data.get("metadata", {})
            rate_headers = metadata.get("headers", {})

            reset_ms = int(rate_headers.get("X-RateLimit-Reset", 0))
            if reset_ms:
                wait_seconds = (reset_ms / 1000) - time.time() + 0.5
                wait_seconds = max(wait_seconds, 1.0)
            else:
                wait_seconds = 2 ** attempt  # Exponential backoff

            if attempt < max_retries:
                time.sleep(wait_seconds)
                continue

        if response.status_code == 402:
            raise Exception("Payment required: insufficient credits")

        response.raise_for_status()

    raise Exception(f"Max retries exceeded")
```

### HTTP Status Codes для Retry

| Code | Retry? | Description |
|------|--------|-------------|
| `429` | Да | Rate limit — ждать по headers |
| `502` | Да | Bad Gateway — retry с backoff |
| `503` | Да | Service Unavailable — retry с backoff |
| `408` | Да | Timeout — retry с backoff |
| `402` | Нет | Payment Required — добавить credits |
| `400` | Нет | Bad Request — исправить запрос |
| `401` | Нет | Unauthorized — проверить API key |

---

## 10. OpenAI SDK Compatibility

### Полная совместимость

OpenRouter **полностью совместим** с OpenAI SDK. Достаточно изменить `base_url`:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="YOUR_OPENROUTER_API_KEY",
    default_headers={
        "HTTP-Referer": "https://your-app.com",  # Optional: для атрибуции
        "X-Title": "Your App Name"               # Optional: для атрибуции
    }
)

# Используем как обычный OpenAI client
response = client.chat.completions.create(
    model="anthropic/claude-4.5-sonnet",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Responses API с OpenAI SDK

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="YOUR_OPENROUTER_API_KEY"
)

# responses.parse() работает!
response = await client.responses.parse(
    model="anthropic/claude-4.5-sonnet",
    instructions="Extract user info",
    input="John is 25 years old",
    text_format=UserSchema,  # Pydantic model
)

print(response.output_parsed)  # Уже Pydantic объект
```

### Structured Output с Instructor

Альтернатива — библиотека [Instructor](https://python.useinstructor.com/integrations/openrouter/):

```python
import instructor
from openai import OpenAI
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

client = instructor.from_provider(
    "openrouter/anthropic/claude-4.5-sonnet",
    base_url="https://openrouter.ai/api/v1",
)

user = client.create(
    messages=[{"role": "user", "content": "Ivan is 28 years old"}],
    response_model=User,
    extra_body={"provider": {"require_parameters": True}}
)

print(user.name)  # "Ivan"
print(user.age)   # 28
```

### Ограничения совместимости

1. **Regex в схемах**: Некоторые модели (OpenAI GPT-4o) не поддерживают regex patterns в structured output
2. **Tool Calling**: Не все модели поддерживают — проверяйте на странице модели
3. **Latency**: OpenRouter добавляет ~25-40ms overhead

---

## 11. Plugins (краткий обзор)

OpenRouter предоставляет плагины для расширения функциональности:

```json
{
  "plugins": [
    {"id": "moderation"},
    {"id": "web", "enabled": true, "max_results": 5},
    {"id": "file-parser", "pdf": {"engine": "mistral-ocr"}},
    {"id": "response-healing", "enabled": true}
  ]
}
```

| Plugin | Description |
|--------|-------------|
| `moderation` | Модерация контента |
| `web` | Web search |
| `file-parser` | Парсинг файлов (PDF) |
| `response-healing` | Исправление битых ответов |

**Для Thing' Sandbox:** Возможно пригодится `response-healing` для structured output.

---

## 12. Сравнение с OpenAI API

| Аспект | OpenAI | OpenRouter |
|--------|--------|------------|
| Base URL | `api.openai.com/v1/responses` | `openrouter.ai/api/v1/responses` |
| Auth | `OPENAI_API_KEY` | `OPENROUTER_API_KEY` |
| `store` | `true`/`false` | только `false` |
| Reasoning effort | до `high` | до `xhigh`, плюс `none` |
| Provider routing | нет | `provider`, `models[]`, `route` |
| Cost tracking | нет | `usage.cost`, `cost_details` |
| Fallback models | нет | `models[]` + `route: "fallback"` |
| Quantization | нет | `provider.quantizations` |

---

## 13. Best Practices

1. **Structured Output**: Всегда используйте `strict: true` для гарантии соответствия схеме

2. **Резервируйте токены**: Для reasoning моделей минимум 25,000 `max_output_tokens`

3. **Provider routing**: Используйте `models[]` с fallback для reliability

4. **Cost tracking**: Используйте `usage.cost` для мониторинга расходов

5. **Data policy**: Если нужен ZDR, используйте `provider.zdr: true`

6. **OpenAI SDK**: Используйте OpenAI SDK с `base_url` — полностью совместим

7. **Rate limits**: Парсите headers из `error.metadata.headers`, не из HTTP headers

---

## 14. ОТВЕТЫ НА ВОПРОСЫ И ОСТАВШИЕСЯ TBD

### ✅ Решено

| Вопрос | Ответ |
|--------|-------|
| **Rate Limit Headers** | Приходят в `error.metadata.headers` при 429. Поля: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (timestamp в ms) |
| **OpenAI SDK Compatibility** | ✅ Полная совместимость. Меняем только `base_url` на `https://openrouter.ai/api/v1` |
| **responses.parse()** | ✅ Работает через OpenAI SDK. Также можно использовать библиотеку Instructor |
| **Store Parameter** | По умолчанию `false`. Responses всё равно сохраняются для `previous_response_id` |

### ⚠️ Требует уточнения (TBD)

#### 1. DELETE Response Endpoint

**Статус:** ❌ НЕ НАЙДЕН в документации

**Проблема:**
- Endpoint `DELETE /v1/responses/{response_id}` не документирован
- Найден только `DELETE /v1/keys/{hash}` для API ключей
- Без DELETE chains будут накапливаться на стороне OpenRouter

**Решения для адаптера:**
1. **Игнорировать** — chains накапливаются, но это проблема OpenRouter
2. **Не использовать chains** — `response_chain_depth = 0` для всех фаз
3. **Уточнить** у OpenRouter support

#### 2. Response Chain Limits

**Неизвестно:**
- Максимальная длина chain
- TTL для сохранённых responses
- Автоматическая очистка старых responses

**Рекомендация:** Использовать короткие chains (depth ≤ 2) до выяснения лимитов

#### 3. Truncation Parameter

**Статус:** Неясно

В OpenAPI схеме `truncation` — пустой объект. В ответе возвращается `"auto"` или `"disabled"`.

**Предположение:** Передавать как объект `{"truncation": {}}` или строку — требует тестирования

#### 4. Reasoning Format

**Частично понятно:**

В `output[].format` для reasoning приходит:
- `openai-responses-v1` — для OpenAI моделей
- `anthropic-claude-v1` — для Claude
- `google-gemini-v1` — для Gemini
- `xai-responses-v1` — для xAI/Grok

**Для адаптера:** Можно игнорировать — формат summary одинаковый

### 📋 План тестирования

Перед реализацией адаптера рекомендуется проверить:

```python
# 1. Проверить работу previous_response_id
response1 = await client.responses.create(...)
response2 = await client.responses.create(
    previous_response_id=response1.id,
    ...
)
# Вопрос: сохраняется ли контекст?

# 2. Проверить DELETE (если существует)
await client.responses.delete(response1.id)
# Вопрос: 404 или работает?

# 3. Проверить truncation
response = await client.responses.create(
    truncation="auto",  # или {"truncation": {}}?
    ...
)

# 4. Проверить rate limit headers при 429
# Симулировать rate limit и проверить структуру error
```

---

## Ссылки

### OpenRouter документация
- [OpenRouter API Overview](https://openrouter.ai/docs/api/reference/overview)
- [OpenRouter Responses API](https://openrouter.ai/docs/api/api-reference/responses/create-responses)
- [OpenRouter Rate Limits](https://openrouter.ai/docs/api/reference/limits)
- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart)
- [OpenRouter FAQ](https://openrouter.ai/docs/faq)
- [OpenRouter Models](https://openrouter.ai/models)

### Structured Output
- [Instructor + OpenRouter Guide](https://python.useinstructor.com/integrations/openrouter/)
- [Pydantic with OpenRouter](https://botflo.com/how-to-use-pydantic-with-openrouter-api/)

### Thing' Sandbox
- OpenAI Reference: `docs/Thing' Sandbox OpenAI Responses API Reference.md`
- LLM Approach: `docs/Thing' Sandbox LLM Approach v2.md`
