# Thing' Sandbox: Архитектура проекта

## 1. Обзор системы

Концепция проекта описана в [Thing' Sandbox Concept.md](Thing'%20Sandbox%20Concept.md).

Этот документ описывает техническую реализацию: структуру проекта, модули, хранение данных и конфигурацию.

Система поддерживает несколько независимых симуляций одновременно.

---

## 2. Структура проекта

```
thing'-sandbox/
├── docs/                     # проектная документация
│   ├── specs/                # спецификации модулей
│   └── tasks/                # задания для Claude Code
│
├── config.toml               # глобальная конфигурация приложения
├── src/
│   ├── schemas/              # JSON-схемы валидации
│   ├── prompts/              # дефолтные промпты
│   ├── utils/                # переиспользуемые компоненты
│   │   ├── __init__.py
│   │   ├── exit_codes.py     # коды завершения
│   │   ├── llm.py            # LLM Client (фасад для фаз)
│   │   ├── llm_errors.py     # иерархия ошибок LLM
│   │   ├── llm_adapters/     # транспортный слой (MVP: только OpenAI)
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # общие типы (AdapterResponse, ResponseUsage)
│   │   │   └── openai.py     # OpenAI Responses API adapter
│   │   └── storage.py        # чтение/запись симуляций
│   ├── __init__.py
│   ├── cli.py                # точка входа (typer)
│   ├── config.py             # загрузка конфигов
│   ├── runner.py             # оркестрация такта
│   ├── phase1.py             # намерения
│   ├── phase2a.py            # разрешение сцены (арбитр)
│   ├── phase2b.py            # генерация нарратива
│   ├── phase3.py             # применение результатов
│   ├── phase4.py             # обновление памяти
│   └── narrators.py          # вывод: console, file, telegram, web
│
├── tests/
│   ├── unit/                 # юнит-тесты
│   ├── integration/          # интеграционные тесты
│   └── conftest.py           # фикстуры pytest
│
├── simulations/              # данные симуляций (в .gitignore)
│
├── requirements.txt          # runtime-зависимости
├── requirements-dev.txt      # dev-зависимости (pytest, mypy, ruff)
├── pyproject.toml            # настройки пакета и инструментов
├── .env.example              # шаблон переменных окружения
├── .gitignore
├── CLAUDE.md                 # инструкция для Claude Code
└── README.md
```

---

## 3. Структура хранения симуляции

### Папка симуляции

```
simulations/
  sim-01/
    simulation.json       # параметры симуляции
    characters/
      bob.json
      elvira.json
    locations/
      tavern.json
      forest.json
    logs/
      tick_000001.md
      tick_000002.md
    prompts/              # опционально, переопределения
      phase2_narrative.md
```

### simulation.json

Параметры симуляции:

```json
{
  "id": "sim-01",
  "current_tick": 42,
  "created_at": "2025-01-15T10:00:00Z",
  "status": "paused"
}
```

### Персонажи и локации

- Каждый персонаж — отдельный JSON файл в `characters/`
- Каждая локация — отдельный JSON файл в `locations/`
- Связи между локациями хранятся внутри локаций (`connections`)
- Текущая локация персонажа хранится внутри персонажа (`state.location`)

### Логи

- Нарративы сохраняются в `logs/` по тактам
- Формат: `tick_NNNNNN.md` (6 цифр, с ведущими нулями)

### Служебные данные LLM (`_openai`)

Entities (персонажи, локации) и `simulation.json` содержат namespace `_openai` для хранения:
- **Response chains** — цепочки `response_id` для контекста между тактами
- **Usage statistics** — накопленная статистика токенов

Пример в `characters/bob.json`:
```json
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

**Важно для реализации фаз:** при вызове `LLMClient` с `entity_key` (например, `"intention:bob"`), клиент автоматически:
1. Извлекает `previous_response_id` из соответствующей chain
2. После успешного ответа добавляет новый `response_id` в chain
3. Накапливает usage статистику

Подробности: [LLM Approach v2 → Хранение состояния](Thing'%20Sandbox%20LLM%20Approach%20v2.md#8-хранение-состояния)

---

## 4. Промпты

### Расположение

- Дефолтные: `src/prompts/`
- Кастомные: `simulations/{sim-id}/prompts/`

### Файлы промптов

```
phase1_intention.md     # фаза 1 — намерение персонажа
phase2_master.md        # фаза 2a — разрешение сцены
phase2_narrative.md     # фаза 2b — генерация нарратива
phase4_summary.md       # фаза 4 — суммаризация памяти
```

### Резолв промпта

1. Ищем `simulations/{sim-id}/prompts/{prompt}.md`
2. Если не найден — берём `src/prompts/{prompt}.md`

Это позволяет переопределять стиль нарратива (фэнтези, киберпанк) для конкретной симуляции, не дублируя все промпты.

---

## 5. Инициализация симуляции

### Создание новой симуляции

При инициализации создаётся папка симуляции со следующим содержимым:

```
simulation-name/
  simulation.json         # current_tick: 0, status: "paused"
  characters/             # начальные персонажи
  locations/              # начальные локации
  logs/                   # пустая папка
```

### Начальное состояние памяти

Память персонажей при инициализации пустая:

```json
"memory": {
  "cells": [],
  "summary": ""
}
```

Пустой массив и пустая строка — проще чем null, не требует проверок.

### Статусы симуляции

| Статус | Значение |
|--------|----------|
| `running` | Такт выполняется прямо сейчас |
| `paused` | Между тактами, готов к продолжению |

Комбинация `current_tick: 0` + `status: "paused"` означает только что созданную симуляцию, в которой ещё не было ни одного такта.

---

## 5.1 Шаблоны и сброс симуляции

### Папка шаблонов

Шаблоны хранятся в `simulations/_templates/`. Префикс `_` исключает
папку из списка активных симуляций.

```
simulations/
  _templates/           # шаблоны
    demo-sim/           # шаблон демо-симуляции
      simulation.json
      characters/
      locations/
      logs/             # пустая папка (.gitkeep)
  demo-sim/             # рабочая копия (мутирует)
```

### Сброс к шаблону

Команда `reset` копирует шаблон поверх рабочей симуляции:

```bash
python -m src.cli reset demo-sim
```

**Поведение:**
- Шаблон существует → копируется поверх рабочей симуляции
- Рабочей симуляции нет → создаётся из шаблона
- Папка `logs/` очищается
- Шаблона нет → ошибка

### Демо-симуляция

`demo-sim` — тестовая симуляция по мотивам "Войны миров" Уэллса.
Шаблон: `simulations/_templates/demo-sim/`.

---

## 6. Атомарность такта

### Принцип

Состояние симуляции обновляется только после полного завершения такта — все 4 фазы выполнены, все валидации пройдены.

### Следствия

- Никаких temp-файлов и промежуточных состояний
- При падении на любой фазе — перезапуск с `current_tick`
- `current_tick` инкрементируется только в самом конце

### Порядок записи в конце такта

1. Обновить `characters/*.json` (состояния + память)
2. Обновить `locations/*.json` (состояния)
3. Записать `logs/tick_NNNNNN.md`
4. Обновить `simulation.json` (инкремент `current_tick`, статус `paused`)

Если падение произошло между пунктами — при следующем запуске `current_tick` не изменился, такт повторяется заново. Частично записанные файлы будут перезаписаны.

---

## 7. Модульная структура

### Иерархия вызовов

- **CLI** — точка входа, вызывает Runner
  - **Runner** — оркестрация такта, вызывает фазы последовательно
    - **Phase 1** — формирование намерений, использует LLM Client
    - **Phase 2a** — разрешение сцен, использует LLM Client
    - **Phase 2b** — генерация нарратива, использует LLM Client
    - **Phase 3** — применение результатов (без LLM)
    - **Phase 4** — обновление памяти, использует LLM Client

### Общие компоненты

Используются на разных уровнях:

- **LLM Client** — используют Phase 1, 2a, 2b, 4
- **Storage** — использует Runner (загрузка/сохранение состояния)
- **Narrators** — использует Runner (вывод после такта)
- **Config** — использует CLI и Runner (параметры, резолв промптов)

### Компоненты

| Компонент | Файл | Ответственность |
|-----------|------|-----------------|
| CLI | `cli.py` | Точка входа, парсит аргументы, вызывает Runner |
| Config | `config.py` | Загрузка конфигурации, PhaseConfig, резолв промптов |
| Runner | `runner.py` | Оркестрация такта, вызывает фазы 1→2a→2b→3→4, атомарность |
| Phase 1 | `phase1.py` | Формирование намерений персонажей |
| Phase 2a | `phase2a.py` | Разрешение сцены арбитром |
| Phase 2b | `phase2b.py` | Генерация нарратива |
| Phase 3 | `phase3.py` | Применение результатов (без LLM) |
| Phase 4 | `phase4.py` | Обновление памяти персонажей |
| LLM Client | `utils/llm.py` | Провайдер-агностичный фасад, batch execution, chains |
| LLM Errors | `utils/llm_errors.py` | Иерархия ошибок LLM |
| LLM Adapter Base | `utils/llm_adapters/base.py` | Общие типы: AdapterResponse, ResponseUsage |
| OpenAI Adapter | `utils/llm_adapters/openai.py` | Транспорт для OpenAI Responses API (MVP адаптер, другие — позже) |
| Storage | `utils/storage.py` | Чтение/запись симуляции |
| Exit Codes | `utils/exit_codes.py` | Стандартные коды завершения |
| Narrators | `narrators.py` | Вывод: console, file, telegram, web |

### Классификация модулей

| Тип | Модули | Особенности спек |
|------|---------|------------------|
| **Phase** | `phase_*.py` | Data Flow, LLM Integration (опционально) |
| **Core** | `cli.py`, `config.py`, `runner.py`, `narrators.py` | Стандартная структура |
| **Utils** | `utils/*.py` | Стандартная структура |

### Спецификации модулей

Спецификации хранятся в `docs/specs/`, именование по типу модуля (phase_, core_, util_).

Гайд по написанию спецификаций: [Thing' Sandbox Specs Writing Guide.md](Thing'%20Sandbox%20Specs%20Writing%20Guide.md)

---

## 8. Схемы данных

Все схемы хранятся в `src/schemas/`.

### Данные симуляции

| Схема | Назначение |
|-------|------------|
| `Character.schema.json` | Персонаж: identity, state, memory |
| `Location.schema.json` | Локация: identity, state, connections |

Эти схемы используют `additionalProperties: true` — гибкость для меты, отладки, расширений.

### Ответы LLM

| Схема | Фаза | Назначение |
|-------|------|------------|
| `IntentionResponse.schema.json` | 1 | Намерение персонажа |
| `Master.schema.json` | 2a | Разрешение сцены арбитром |
| `NarrativeResponse.schema.json` | 2b | Нарратив для лога |
| `SummaryResponse.schema.json` | 4 | Суммаризация памяти |

Эти схемы используют `additionalProperties: false` — строгий контракт, валидация через OpenAI structured output.

---

## 9. Конфигурация

### Разделение конфигурации

| Файл | Что хранит | Пример |
|------|------------|--------|
| `.env` | Секреты | `OPENAI_API_KEY`, `TELEGRAM_TOKEN` |
| `config.toml` | Параметры приложения | Параметры LLM, дефолты симуляции |
| `simulation.json` | Параметры симуляции | `current_tick`, `status` |

### config.toml

Глобальная конфигурация в корне проекта. Загружается через `src/config.py` (Pydantic Settings).

Секции конфига:
- `[simulation]` — дефолтные параметры симуляций (memory_cells и др.)
- `[phase1]`, `[phase2a]`, `[phase2b]`, `[phase4]` — параметры LLM для каждой фазы

### PhaseConfig

Каждая фаза с LLM имеет свою секцию конфига. Параметры включают: model, timeout, max_retries, reasoning_effort, response_chain_depth и др.

Подробности: [LLM Approach v2 → Конфигурация](Thing'%20Sandbox%20LLM%20Approach%20v2.md#11-конфигурация)

### Резолв промптов

Config предоставляет функцию резолва промптов:

1. Ищем `simulations/{sim-id}/prompts/{prompt}.md`
2. Если не найден — берём `src/prompts/{prompt}.md`

Это позволяет переопределять стиль нарратива для конкретной симуляции.

---

## 10. Коды завершения (Exit Codes)

Стандартные коды завершения для CLI. Полная спецификация: [util_exit_codes.md](specs/util_exit_codes.md)

| Код | Константа | Когда использовать |
|-----|----------|--------------------|
| 0 | `EXIT_SUCCESS` | Успешное завершение |
| 1 | `EXIT_CONFIG_ERROR` | Нет API key, битый config.toml |
| 2 | `EXIT_INPUT_ERROR` | Битые JSON персонажей/локаций, невалидные схемы |
| 3 | `EXIT_RUNTIME_ERROR` | LLM вернул мусор после retry, неожиданные исключения |
| 4 | `EXIT_API_LIMIT_ERROR` | Rate limits OpenAI |
| 5 | `EXIT_IO_ERROR` | Не смог записать в simulations/ |

---

## 11. Поток такта: технические детали

Логика фаз и стоимость такта описаны в [Concept](Thing'%20Sandbox%20Concept.md#2-структура-такта-четыре-фазы). Здесь — только маппинг на схемы данных.

| Фаза | Запросов | Схема ответа LLM |
|------|----------|------------------|
| 1 — Намерения | N | `IntentionResponse.schema.json` |
| 2a — Разрешение | L | `Master.schema.json` |
| 2b — Нарратив | L | `NarrativeResponse.schema.json` |
| 3 — Применение | 0 | — (механика) |
| 4 — Память | N | `SummaryResponse.schema.json` |

---

## 12. Технологический стек

### Язык и рантайм

| Компонент | Решение |
|-----------|---------|
| Язык | Python 3.11+ |
| Менеджер зависимостей | pip + requirements.txt |
| Типизация | Type hints + mypy |

### Основные библиотеки

| Назначение | Библиотека | Зачем |
|------------|------------|-------|
| CLI | typer | Современный CLI с type hints |
| Валидация/модели | Pydantic v2 | Модели данных, загрузка конфигов |
| LLM | openai (официальный SDK) | Structured output из коробки |
| Web-сервер | FastAPI | Async, websockets, Pydantic-native |
| Telegram | python-telegram-bot | Зрелая библиотека (альтернатива: aiogram) |

### Dev-инструменты

| Назначение | Инструмент |
|------------|------------|
| Тесты | pytest |
| Типы | mypy |
| Линтер/форматтер | ruff |

### Конфигурация

| Тип | Формат | Где |
|-----|--------|-----|
| Секреты | .env | OPENAI_API_KEY, TELEGRAM_TOKEN |
| Параметры приложения | config.toml | src/config.py (Pydantic Settings) |
| Параметры симуляции | simulation.json | simulations/{id}/simulation.json |

### Интерфейсы вывода (Narrators)

| Интерфейс | Тип | Приоритет |
|-----------|-----|----------|
| Console | pull (print) | MVP |
| File | write | MVP |
| Telegram | push | после MVP |
| Web | push (websocket) | после MVP |

---

## Примечания

- Документ обновляется по мере развития проекта
- Детали работы с LLM: [Thing' Sandbox LLM Approach v2.md](Thing'%20Sandbox%20LLM%20Approach%20v2.md)
- Спецификации модулей: `docs/specs/`
