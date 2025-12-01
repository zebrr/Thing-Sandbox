# Thing' Sandbox: План разработки v1.1

## Обзор

План разбит на две части:
- **Часть A: Инфраструктура** — фундамент проекта, стабильная основа
- **Часть B: Vertical Slices** — итеративное наращивание функционала с работающим результатом на каждом этапе

### Принципы верификации

После каждого этапа выполняется проверка:
1. Claude App читает отчёт Claude Code (`TS-*_REPORT.md`)
2. Проверяет созданные или обновлённые спецификации
3. При любых сомнениях — смотрит код и тесты напрямую
4. Статус меняется на "готов" только после успешной верификации
5. Запуски утилит осуществляет пользователь
6. Контрольные запуски тестов по просьбе Claude App осуществляет пользователь

---

## Часть A: Инфраструктура

### A.1: Инициализировать проект

Создание структуры проекта, настройка инструментов и зависимостей.

**STATUS: готов**

**Входные требования:**
- Архитектура проекта готова (`docs/Thing' Sandbox Architecture.md`)

**Задачи:**
- Создать `pyproject.toml` — метаданные пакета, настройки ruff/mypy/pytest
- Создать `requirements.txt` — runtime зависимости (typer, pydantic, openai, jsonschema)
- Создать `requirements-dev.txt` — dev зависимости (pytest, pytest-cov, mypy, ruff)
- Создать `.env.example` — шаблон переменных окружения
- Создать `config.toml` — дефолтная конфигурация приложения
- Создать структуру `src/` с `__init__.py` файлами
- Создать структуру `tests/` с `conftest.py`
- Создать папку `src/prompts/` (пустая, для будущих дефолтных промптов)

**Ожидаемый результат:**
```bash
pip install -r requirements.txt      # работает
pip install -r requirements-dev.txt  # работает
ruff check src/                      # запускается (пусть на пустых файлах)
mypy src/                            # запускается
pytest                               # запускается (0 тестов)
```

**Артефакты:**
- Задание: `docs/tasks/TS-A.1-INIT-001.md`
- Отчёт: `docs/tasks/TS-A.1-INIT-001_REPORT.md`
- Файлы: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.env.example`, `config.toml`, `README.md`
- Структура: `src/__init__.py`, `src/utils/__init__.py`, `src/prompts/`, `tests/conftest.py`

---

### A.2: Реализовать модуль Exit Codes

Стандартные коды завершения для CLI — единообразная обработка ошибок.

**STATUS: готов**

**Входные требования:**
- A.1 готов
- Спецификация `docs/specs/util_exit_codes.md` существует

**Задачи:**
- Реализовать `src/utils/exit_codes.py` по существующей спецификации
- Написать юнит-тесты

**Ожидаемый результат:**
- Модуль импортируется: `from src.utils.exit_codes import EXIT_SUCCESS`
- Все константы и функции работают по спеке
- Тесты проходят

**Артефакты:**
- Задание: `docs/tasks/TS-A.2-EXIT-001.md`
- Отчёт: `docs/tasks/TS-A.2-EXIT-001_REPORT.md`
- Спецификация: `docs/specs/util_exit_codes.md` (обновить статус на READY)
- Модуль: `src/utils/exit_codes.py`
- Тесты: `tests/unit/test_exit_codes.py`

---

### A.3: Спроектировать и реализовать модуль Config

Загрузка конфигурации из `config.toml` и `.env`, резолв промптов.

**STATUS: готов**

**Входные требования:**
- A.1 готов

**Задачи:**
- Написать спецификацию `docs/specs/core_config.md`
- Реализовать `src/config.py`:
  - Загрузка `config.toml` через Pydantic Settings
  - Загрузка `.env` (API keys)
  - Функция резолва промптов: simulation override → default
  - Валидация конфигурации
- Написать юнит-тесты

**Ожидаемый результат:**
```python
from src.config import Config

config = Config.load()
prompt_path = config.resolve_prompt("phase1_intention", sim_path)
```

**Артефакты:**
- Задание: `docs/tasks/TS-A.3-CONFIG-001.md`
- Отчёт: `docs/tasks/TS-A.3-CONFIG-001_REPORT.md`
- Спецификация: `docs/specs/core_config.md`
- Модуль: `src/config.py`
- Тесты: `tests/unit/test_config.py`

---

### A.4: Спроектировать и реализовать модуль Storage

Чтение/запись симуляций, валидация по JSON-схемам, Pydantic-модели данных.

**STATUS: готов**

**Входные требования:**
- A.1 готов
- JSON-схемы существуют в `src/schemas/`

**Задачи:**
- Написать спецификацию `docs/specs/util_storage.md`
- Реализовать `src/utils/storage.py`:
  - `load_simulation(path)` — загрузка simulation.json + characters + locations
  - `save_simulation(path, simulation)` — атомарное сохранение
  - Валидация по JSON-схемам
  - Pydantic-модели для Simulation, Character, Location
- Написать юнит-тесты

**Ожидаемый результат:**
```python
from src.utils.storage import load_simulation, save_simulation

sim = load_simulation(Path("simulations/test-sim"))
sim.current_tick += 1
save_simulation(Path("simulations/test-sim"), sim)
```

**Артефакты:**
- Задание: `docs/tasks/TS-A.4-STORAGE-001.md`
- Отчёт: `docs/tasks/TS-A.4-STORAGE-001_REPORT.md`
- Спецификация: `docs/specs/util_storage.md`
- Модуль: `src/utils/storage.py`
- Тесты: `tests/unit/test_storage.py`

---

### A.5a: Расширить модуль Config (Phase Config)

Добавление конфигурации фаз LLM: модели, таймауты, retry, параметры reasoning.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox LLM Approach v2.md` (раздел 11 — Конфигурация)
- Текущая спека: `docs/specs/core_config.md`

**Входные требования:**
- A.3 (Config) готов

**Задачи:**
- Обновить спецификацию `docs/specs/core_config.md`:
  - Добавить PhaseConfig модель
  - Добавить Config.phase1, Config.phase2a, Config.phase2b, Config.phase4 атрибуты
- Обновить `config.toml`:
  - Добавить секции `[phase1]`, `[phase2a]`, `[phase2b]`, `[phase4]`
  - Параметры: model, is_reasoning, max_context_tokens, max_completion, timeout, max_retries, reasoning_effort, reasoning_summary, verbosity, truncation, response_chain_depth
- Обновить `src/config.py`:
  - Добавить `PhaseConfig` Pydantic модель
  - Загрузка секций phase1-4 в Config
  - Валидация параметров
- Обновить `tests/unit/test_config.py`:
  - Тесты загрузки PhaseConfig
  - Тесты валидации (невалидные значения)
  - Тесты дефолтов

**Ожидаемый результат:**
```python
from src.config import Config

config = Config.load()
print(config.phase1.model)           # "gpt-5-mini-2025-08-07"
print(config.phase1.timeout)         # 600
print(config.phase2a.response_chain_depth)  # 2
```

**Артефакты:**
- Задание: `docs/tasks/TS-A.5a-CONFIG-001.md`
- Отчёт: `docs/tasks/TS-A.5a-CONFIG-001_REPORT.md`
- Спецификация: `docs/specs/core_config.md` (обновить)
- Модуль: `src/config.py` (обновить)
- Конфиг: `config.toml` (обновить)
- Тесты: `tests/unit/test_config.py` (обновить)

---

### A.5b: Реализовать OpenAI Adapter (транспортный слой)

Адаптер для OpenAI Responses API: выполнение запросов, retry, timeout, rate limit handling.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox LLM Approach v2.md` (разделы 2, 4, 9)
- API референс: `docs/Thing' Sandbox OpenAI Responses API Reference.md`
- Structured Outputs: `docs/Thing' Sandbox OpenAI Structured model outputs API Reference.md`

**Входные требования:**
- A.5a (Phase Config) готов

**Задачи:**
- Написать спецификацию `docs/specs/util_llm_adapter.md`
- Реализовать `src/utils/llm_errors.py`:
  - Иерархия ошибок: `LLMError`, `LLMRefusalError`, `LLMIncompleteError`, `LLMRateLimitError`, `LLMTimeoutError`
- Реализовать `src/utils/llm_adapters/base.py`:
  - `BaseAdapter` — абстрактный интерфейс адаптера
  - `AdapterResponse` — dataclass с response_id, parsed, usage, headers
  - `ResponseUsage` — dataclass для статистики токенов
- Реализовать `src/utils/llm_adapters/openai.py`:
  - `OpenAIAdapter` — реализация для OpenAI Responses API
  - Timeout через `httpx.Timeout`
  - Retry для rate limit и transient errors (молча, внутри `execute()`)
  - Обработка статусов: completed, incomplete, failed, refusal
  - `delete_response()` с логированием ошибок
- Написать юнит-тесты (mock AsyncOpenAI)
- Написать интеграционные тесты (реальный API)

**Ожидаемый результат:**
```python
from src.utils.llm_adapters.openai import OpenAIAdapter
from src.config import Config

config = Config.load()
adapter = OpenAIAdapter(config.phase1)

response = await adapter.execute(
    instructions="You are a helpful assistant",
    input_data="Hello",
    schema={"type": "object", "properties": {...}}
)
# response.parsed — dict с ответом
# response.usage — статистика токенов
```

**Примечание:** Интеграционные тесты требуют `OPENAI_API_KEY` в окружении.

**Артефакты:**
- Задание: `docs/tasks/TS-A.5b-ADAPTER-001.md`
- Отчёт: `docs/tasks/TS-A.5b-ADAPTER-001_REPORT.md`
- Спецификация: `docs/specs/util_llm_adapter.md`
- Модули:
  - `src/utils/llm_errors.py`
  - `src/utils/llm_adapters/__init__.py`
  - `src/utils/llm_adapters/base.py`
  - `src/utils/llm_adapters/openai.py`
- Тесты: `tests/unit/test_llm_adapter.py`, `tests/integration/test_llm_adapter_integration.py`

---

### A.5c: Реализовать LLM Client (фасад для фаз)

Провайдер-агностичный клиент: batch execution, chains, usage accumulation.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox LLM Approach v2.md` (разделы 3, 5, 7, 8)
- Structured Outputs: `docs/Thing' Sandbox OpenAI Structured model outputs API Reference.md`

**Входные требования:**
- A.5b готов

**Задачи:**
- Написать спецификацию `docs/specs/util_llm.md`
- Реализовать `src/utils/llm.py`:
  - `LLMRequest` — dataclass для запроса
  - `LLMClient` — провайдер-агностичный фасад:
    - `create_response()` — единичный запрос
    - `create_batch()` — параллельные запросы через `asyncio.gather()`
  - `ResponseChainManager` — управление цепочками per entity:
    - Мутирует entities in-place
    - Auto-confirm при успешном ответе
    - Возвращает evicted response_id для удаления
  - Pydantic → JSON Schema конверсия
  - Usage accumulation в `entity._openai.usage`
- Написать юнит-тесты (mock adapter)

**Ожидаемый результат:**
```python
from src.utils.llm import LLMClient, LLMRequest

client = LLMClient(adapter, entities)

# Единичный запрос
response = await client.create_response(
    instructions="Generate intention",
    input_data="Character context...",
    schema=IntentionResponse,
    entity_key="intention:bob"
)

# Batch запросов
requests = [LLMRequest(...) for char in characters]
results = await client.create_batch(requests)
# results — list[IntentionResponse | LLMError]
```

**Артефакты:**
- Задание: `docs/tasks/TS-A.5c-LLM-001.md`
- Отчёт: `docs/tasks/TS-A.5c-LLM-001_REPORT.md`
- Спецификация: `docs/specs/util_llm.md`
- Модуль: `src/utils/llm.py`
- Тесты: `tests/unit/test_llm.py`

---

## Часть B: Vertical Slices

### B.0: Собрать скелет системы (Runner + CLI + стабы фаз)

Оркестрация такта, CLI-точка входа, заглушки фаз с хардкодом.

**STATUS: не готов**

**Входные требования:**
- Часть A полностью готова

**Задачи:**
- **Обновление конфигурации:**
  - Обновить `config.toml` — добавить секцию `[simulation]` (memory_cells и другие дефолты тактов)
  - Обновить `src/config.py` — добавить `SimulationConfig` Pydantic модель
  - Обновить `tests/unit/test_config.py` — покрыть новые параметры
- Написать спецификации:
  - `docs/specs/core_runner.md`
  - `docs/specs/core_cli.md`
  - `docs/specs/core_narrators.md`
- Реализовать `src/runner.py`:
  - Оркестрация такта: загрузка → фазы 1-4 → сохранение
  - Атомарность: всё или ничего
  - Вызов Narrators после такта
- Реализовать `src/cli.py`:
  - Команда `run <sim-id>` — запуск одного такта
  - Команда `status <sim-id>` — статус симуляции (stub)
- Реализовать `src/narrators.py`:
  - `ConsoleNarrator` — вывод в консоль
- Создать стабы фаз (`src/phase1.py`, `src/phase2a.py`, `src/phase2b.py`, `src/phase3.py`, `src/phase4.py`):
  - Возвращают захардкоженные данные
- Создать тестовую симуляцию `simulations/test-sim/`

**Ожидаемый результат:**
```bash
python -m src.cli run test-sim
# Выводит фейковый нарратив в консоль
# simulation.json обновляется (current_tick: 0 → 1)
```

**Артефакты:**
- Задание: `docs/tasks/TS-B.0-SKELETON-001.md`
- Отчёт: `docs/tasks/TS-B.0-SKELETON-001_REPORT.md`
- Спецификации: `docs/specs/core_runner.md`, `docs/specs/core_cli.md`, `docs/specs/core_narrators.md`
- Модули: `src/runner.py`, `src/cli.py`, `src/narrators.py`
- Стабы: `src/phase1.py`, `src/phase2a.py`, `src/phase2b.py`, `src/phase3.py`, `src/phase4.py`
- Тестовые данные: `simulations/test-sim/`
- Тесты: `tests/integration/test_skeleton.py`

---

### B.1a: Спроектировать промпт Phase 1 (намерения)

Разработка промпта для генерации намерений персонажей.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox Concept.md`
- Схема ответа: `src/schemas/IntentionResponse.schema.json`

**Входные требования:**
- B.0 готов
- Концепция проекта изучена

**Задачи:**
- Разработать промпт `src/prompts/phase1_intention.md`:
  - Системная инструкция для персонажа
  - Формат входных данных (контекст, память, локация)
  - Требования к выходу (IntentionResponse schema)
- Протестировать промпт вручную в ChatGPT/Claude
- Задокументировать примеры хороших/плохих ответов

**Ожидаемый результат:**
- Файл промпта готов
- Промпт генерирует осмысленные намерения при ручном тестировании

**Артефакты:**
- Промпт: `src/prompts/phase1_intention.md`

---

### B.1b: Реализовать Phase 1 (намерения)

Фаза 1 — сборка контекста, вызов LLM, валидация ответа, graceful degradation.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox LLM Approach v2.md` (раздел 10 — Graceful Degradation)
- Схема ответа: `src/schemas/IntentionResponse.schema.json`

**Входные требования:**
- B.1a готов (промпт разработан)

**Задачи:**
- Написать спецификацию `docs/specs/phase_1.md`
- Реализовать `src/phase1.py`:
  - Сборка контекста для персонажа (identity, state, memory, location)
  - Вызов LLMClient с промптом
  - Валидация ответа по `IntentionResponse.schema.json`
  - **Fallback:** при `LLMError` → `intention: "idle"` + warning в лог
- Написать юнит-тесты
- Написать интеграционный тест с реальным LLM

**Ожидаемый результат:**
- Персонажи генерируют осмысленные намерения
- При сбое LLM персонаж "замирает" (idle), симуляция продолжается
- В консоли видим реальные намерения (остальные фазы — стабы)

**Артефакты:**
- Задание: `docs/tasks/TS-B.1b-PHASE1-001.md`
- Отчёт: `docs/tasks/TS-B.1b-PHASE1-001_REPORT.md`
- Спецификация: `docs/specs/phase_1.md`
- Модуль: `src/phase1.py`
- Тесты: `tests/unit/test_phase1.py`, `tests/integration/test_phase1_integration.py`

---

### B.2: Реализовать Phase 3 (применение результатов)

Фаза 3 — применение решений арбитра к состоянию симуляции (без LLM).

**STATUS: не готов**

**Ключевые документы:**
- Схема входа: `src/schemas/Master.schema.json`

**Входные требования:**
- B.1b готов

**Задачи:**
- Написать спецификацию `docs/specs/phase_3.md`
- Реализовать `src/phase3.py`:
  - Применение `Master.schema.json` к состоянию симуляции
  - Обновление персонажей (location, internal_state, external_intent)
  - Добавление memory_entry в очередь памяти
  - Обновление локаций (moment, description)
- Написать юнит-тесты с разными сценариями

**Ожидаемый результат:**
- Состояние симуляции корректно обновляется по результатам арбитра
- Перемещение персонажей работает
- Память накапливается

**Артефакты:**
- Задание: `docs/tasks/TS-B.2-PHASE3-001.md`
- Отчёт: `docs/tasks/TS-B.2-PHASE3-001_REPORT.md`
- Спецификация: `docs/specs/phase_3.md`
- Модуль: `src/phase3.py`
- Тесты: `tests/unit/test_phase3.py`

---

### B.3a: Спроектировать промпты Phase 2 (арбитр и нарратив)

Разработка промптов для арбитра и генерации нарратива.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox Concept.md`
- Схема арбитра: `src/schemas/Master.schema.json`
- Схема нарратива: `src/schemas/NarrativeResponse.schema.json`

**Входные требования:**
- B.2 готов

**Задачи:**
- Разработать промпт `src/prompts/phase2_master.md`:
  - Инструкция для арбитра
  - Формат входных данных (локация, персонажи, намерения)
  - Требования к выходу (Master.schema.json)
- Разработать промпт `src/prompts/phase2_narrative.md`:
  - Инструкция для генерации нарратива
  - Формат входных данных (результат арбитра + контекст)
  - Требования к выходу (NarrativeResponse.schema.json)
- Протестировать промпты вручную

**Ожидаемый результат:**
- Файлы промптов готовы
- Арбитр разрешает конфликты осмысленно
- Нарратив читаемый и интересный

**Артефакты:**
- Промпты: `src/prompts/phase2_master.md`, `src/prompts/phase2_narrative.md`

---

### B.3b: Реализовать Phase 2a и 2b (арбитр и нарратив)

Фазы 2a/2b — разрешение сцены и генерация человекочитаемого описания, graceful degradation.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox LLM Approach v2.md` (раздел 10 — Graceful Degradation)
- Схема арбитра: `src/schemas/Master.schema.json`
- Схема нарратива: `src/schemas/NarrativeResponse.schema.json`

**Входные требования:**
- B.3a готов (промпты разработаны)

**Задачи:**
- Написать спецификации:
  - `docs/specs/phase_2a.md`
  - `docs/specs/phase_2b.md`
- Реализовать `src/phase2a.py` (арбитр):
  - Сборка контекста локации + все намерения персонажей
  - Вызов LLMClient
  - Валидация по `Master.schema.json`
  - **Fallback:** при `LLMError` → `MasterResponse.empty_fallback()` + warning
- Реализовать `src/phase2b.py` (нарратив):
  - Генерация человекочитаемого описания
  - Валидация по `NarrativeResponse.schema.json`
  - **Fallback:** при `LLMError` → `"[Тишина в локации]"` + warning
- Написать тесты

**Ожидаемый результат:**
- Полный цикл: намерения → разрешение → нарратив
- При сбое арбитра — "ничего не произошло", симуляция продолжается
- Нарратив осмысленный, отражает события сцены

**Артефакты:**
- Задание: `docs/tasks/TS-B.3b-PHASE2-001.md`
- Отчёт: `docs/tasks/TS-B.3b-PHASE2-001_REPORT.md`
- Спецификации: `docs/specs/phase_2a.md`, `docs/specs/phase_2b.md`
- Модули: `src/phase2a.py`, `src/phase2b.py`
- Тесты: `tests/unit/test_phase2a.py`, `tests/unit/test_phase2b.py`, `tests/integration/test_phase2_integration.py`

---

### B.4a: Спроектировать промпт Phase 4 (память)

Разработка промпта для суммаризации памяти персонажей.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox Concept.md`
- Схема ответа: `src/schemas/SummaryResponse.schema.json`

**Входные требования:**
- B.3b готов

**Задачи:**
- Разработать промпт `src/prompts/phase4_summary.md`:
  - Инструкция для суммаризации памяти
  - Формат входных данных (старый summary + выпадающая ячейка)
  - Требования к выходу (SummaryResponse.schema.json)
  - Принципы сжатия: что сохранять, что можно потерять
- Протестировать промпт вручную

**Ожидаемый результат:**
- Файл промпта готов
- Суммаризация сохраняет ключевые события
- Старые события размываются естественно

**Артефакты:**
- Промпт: `src/prompts/phase4_summary.md`

---

### B.4b: Реализовать Phase 4 (память)

Фаза 4 — FIFO-сдвиг ячеек памяти, суммаризация выпадающих событий, graceful degradation.

**STATUS: не готов**

**Ключевые документы:**
- Концепция: `docs/Thing' Sandbox LLM Approach v2.md` (раздел 10 — Graceful Degradation)
- Схема ответа: `src/schemas/SummaryResponse.schema.json`

**Входные требования:**
- B.4a готов (промпт разработан)

**Задачи:**
- Написать спецификацию `docs/specs/phase_4.md`
- Реализовать `src/phase4.py`:
  - Суммаризация: summary + выпадающая ячейка K → новый summary
  - FIFO-сдвиг ячеек памяти
  - Добавление новой записи (memory_entry) в ячейку 0
  - Вызов LLMClient для суммаризации
  - **Fallback:** при `LLMError` → оставить старую память + warning
- Написать тесты

**Ожидаемый результат:**
- Персонажи накапливают память
- Summary корректно сжимается
- FIFO работает правильно
- При сбое LLM память не обновляется, симуляция продолжается

**Артефакты:**
- Задание: `docs/tasks/TS-B.4b-PHASE4-001.md`
- Отчёт: `docs/tasks/TS-B.4b-PHASE4-001_REPORT.md`
- Спецификация: `docs/specs/phase_4.md`
- Модуль: `src/phase4.py`
- Тесты: `tests/unit/test_phase4.py`, `tests/integration/test_phase4_integration.py`

---

### B.5: Отполировать MVP

FileNarrator, команды `init`/`status`, полная обработка ошибок.

**STATUS: не готов**

**Входные требования:**
- B.4b готов

**Задачи:**
- **Обновление конфигурации (при необходимости):**
  - Обновить `config.toml` — добавить секции для narrators/logging если нужно
  - Обновить `src/config.py` — добавить соответствующие Pydantic модели
  - Обновить `tests/unit/test_config.py` — покрыть новые параметры
- Реализовать `FileNarrator`:
  - Запись логов в `logs/tick_NNNNNN.md`
- Добавить команду CLI `init <sim-id>`:
  - Создание новой симуляции из шаблона
- Улучшить команду `status <sim-id>`:
  - Показать current_tick, количество персонажей/локаций
- Полная обработка ошибок:
  - Все exit codes используются корректно
  - Понятные сообщения об ошибках
- Интеграционные тесты на несколько тактов подряд

**Ожидаемый результат:**
```bash
# Создать симуляцию
python -m src.cli init my-sim --template fantasy

# Запустить 5 тактов
for i in {1..5}; do python -m src.cli run my-sim; done

# Проверить статус
python -m src.cli status my-sim
# Output: my-sim: tick 5, 3 characters, 2 locations, status: paused

# Прочитать логи
cat simulations/my-sim/logs/tick_000005.md
```

**Артефакты:**
- Задание: `docs/tasks/TS-B.5-MVP-001.md`
- Отчёт: `docs/tasks/TS-B.5-MVP-001_REPORT.md`
- Модуль: `src/narrators.py` (добавить `FileNarrator`)
- Модуль: `src/cli.py` (добавить команды `init`, улучшить `status`)
- Тесты: `tests/integration/test_mvp.py`
- Документация: `README.md` (обновить с примерами использования)
