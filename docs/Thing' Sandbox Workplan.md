# Thing' Sandbox: План разработки v1.0

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
- Задание: `docs/tasks/TS-INIT-001.md`
- Отчёт: `docs/tasks/TS-INIT-001_REPORT.md`
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
- Задание: `docs/tasks/TS-EXIT-001.md`
- Отчёт: `docs/tasks/TS-EXIT-001_REPORT.md`
- Спецификация: `docs/specs/util_exit_codes.md` (обновить статус на READY)
- Модуль: `src/utils/exit_codes.py`
- Тесты: `tests/unit/test_exit_codes.py`

---

### A.3: Спроектировать и реализовать модуль Config

Загрузка конфигурации из `config.toml` и `.env`, резолв промптов.

**STATUS: не готов**

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
- Задание: `docs/tasks/TS-CONFIG-001.md`
- Отчёт: `docs/tasks/TS-CONFIG-001_REPORT.md`
- Спецификация: `docs/specs/core_config.md`
- Модуль: `src/config.py`
- Тесты: `tests/unit/test_config.py`

---

### A.4: Спроектировать и реализовать модуль Storage

Чтение/запись симуляций, валидация по JSON-схемам, Pydantic-модели данных.

**STATUS: не готов**

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
- Задание: `docs/tasks/TS-STORAGE-001.md`
- Отчёт: `docs/tasks/TS-STORAGE-001_REPORT.md`
- Спецификация: `docs/specs/util_storage.md`
- Модуль: `src/utils/storage.py`
- Тесты: `tests/unit/test_storage.py`

---

### A.5: Спроектировать и реализовать модуль LLM Client

Единый интерфейс для вызовов OpenAI: structured output, retry, rate limits.

**STATUS: не готов**

**Входные требования:**
- A.1 готов
- A.3 (Config) готов

**Задачи:**
- Написать спецификацию `docs/specs/util_llm.md`
- **Обновление конфигурации:**
  - Обновить `config.toml` — добавить секцию `[llm]` (model, timeout, max_retries, retry_delay)
  - Обновить `src/config.py` — добавить `LLMConfig` Pydantic модель
  - Обновить `tests/unit/test_config.py` — покрыть новые параметры
- Реализовать `src/utils/llm.py`:
  - Единый интерфейс `LLMClient` для вызова OpenAI
  - Structured output через `response_format` (JSON schema)
  - Retry с exponential backoff
  - Обработка rate limits
  - Логирование запросов/ответов
- Написать юнит-тесты (с мок-клиентом)
- Написать интеграционные тесты (с реальным API)

**Ожидаемый результат:**
```python
from src.utils.llm import LLMClient

client = LLMClient(config)
response = client.complete(
    prompt="Generate character intention",
    schema=IntentionResponse,  # Pydantic model или JSON schema
)
```

**Примечание:** Интеграционные тесты требуют `OPENAI_API_KEY` в окружении. Запуск:
```bash
# Только юнит-тесты
pytest tests/unit/test_llm.py -v

# Только интеграционные
pytest tests/integration/test_llm_integration.py -v -m integration

# Пропустить интеграционные если нет ключа
pytest -v -m "not integration"
```

**Артефакты:**
- Задание: `docs/tasks/TS-LLM-001.md`
- Отчёт: `docs/tasks/TS-LLM-001_REPORT.md`
- Спецификация: `docs/specs/util_llm.md`
- Модуль: `src/utils/llm.py`
- Тесты: `tests/unit/test_llm.py`, `tests/integration/test_llm_integration.py`

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
- Задание: `docs/tasks/TS-SKELETON-001.md`
- Отчёт: `docs/tasks/TS-SKELETON-001_REPORT.md`
- Спецификации: `docs/specs/core_runner.md`, `docs/specs/core_cli.md`, `docs/specs/core_narrators.md`
- Модули: `src/runner.py`, `src/cli.py`, `src/narrators.py`
- Стабы: `src/phase1.py`, `src/phase2a.py`, `src/phase2b.py`, `src/phase3.py`, `src/phase4.py`
- Тестовые данные: `simulations/test-sim/`
- Тесты: `tests/integration/test_skeleton.py`

---

### B.1a: Спроектировать промпт Phase 1 (намерения)

Разработка промпта для генерации намерений персонажей.

**STATUS: не готов**

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

Фаза 1 — сборка контекста, вызов LLM, валидация ответа.

**STATUS: не готов**

**Входные требования:**
- B.1a готов (промпт разработан)

**Задачи:**
- Написать спецификацию `docs/specs/phase_1.md`
- Реализовать `src/phase1.py`:
  - Сборка контекста для персонажа (identity, state, memory, location)
  - Вызов LLMClient с промптом
  - Валидация ответа по `IntentionResponse.schema.json`
  - Обработка ошибок
- Написать юнит-тесты
- Написать интеграционный тест с реальным LLM

**Ожидаемый результат:**
- Персонажи генерируют осмысленные намерения
- В консоли видим реальные намерения (остальные фазы — стабы)

**Артефакты:**
- Задание: `docs/tasks/TS-PHASE1-001.md`
- Отчёт: `docs/tasks/TS-PHASE1-001_REPORT.md`
- Спецификация: `docs/specs/phase_1.md`
- Модуль: `src/phase1.py`
- Тесты: `tests/unit/test_phase1.py`, `tests/integration/test_phase1_integration.py`

---

### B.2: Реализовать Phase 3 (применение результатов)

Фаза 3 — применение решений арбитра к состоянию симуляции (без LLM).

**STATUS: не готов**

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
- Задание: `docs/tasks/TS-PHASE3-001.md`
- Отчёт: `docs/tasks/TS-PHASE3-001_REPORT.md`
- Спецификация: `docs/specs/phase_3.md`
- Модуль: `src/phase3.py`
- Тесты: `tests/unit/test_phase3.py`

---

### B.3a: Спроектировать промпты Phase 2 (арбитр и нарратив)

Разработка промптов для арбитра и генерации нарратива.

**STATUS: не готов**

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

Фазы 2a/2b — разрешение сцены и генерация человекочитаемого описания.

**STATUS: не готов**

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
- Реализовать `src/phase2b.py` (нарратив):
  - Генерация человекочитаемого описания
  - Валидация по `NarrativeResponse.schema.json`
- Написать тесты

**Ожидаемый результат:**
- Полный цикл: намерения → разрешение → нарратив
- Нарратив осмысленный, отражает события сцены

**Артефакты:**
- Задание: `docs/tasks/TS-PHASE2-001.md`
- Отчёт: `docs/tasks/TS-PHASE2-001_REPORT.md`
- Спецификации: `docs/specs/phase_2a.md`, `docs/specs/phase_2b.md`
- Модули: `src/phase2a.py`, `src/phase2b.py`
- Тесты: `tests/unit/test_phase2a.py`, `tests/unit/test_phase2b.py`, `tests/integration/test_phase2_integration.py`

---

### B.4a: Спроектировать промпт Phase 4 (память)

Разработка промпта для суммаризации памяти персонажей.

**STATUS: не готов**

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

Фаза 4 — FIFO-сдвиг ячеек памяти, суммаризация выпадающих событий.

**STATUS: не готов**

**Входные требования:**
- B.4a готов (промпт разработан)

**Задачи:**
- Написать спецификацию `docs/specs/phase_4.md`
- Реализовать `src/phase4.py`:
  - Суммаризация: summary + выпадающая ячейка K → новый summary
  - FIFO-сдвиг ячеек памяти
  - Добавление новой записи (memory_entry) в ячейку 0
  - Вызов LLMClient для суммаризации
- Написать тесты

**Ожидаемый результат:**
- Персонажи накапливают память
- Summary корректно сжимается
- FIFO работает правильно

**Артефакты:**
- Задание: `docs/tasks/TS-PHASE4-001.md`
- Отчёт: `docs/tasks/TS-PHASE4-001_REPORT.md`
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
- Задание: `docs/tasks/TS-MVP-001.md`
- Отчёт: `docs/tasks/TS-MVP-001_REPORT.md`
- Модуль: `src/narrators.py` (добавить `FileNarrator`)
- Модуль: `src/cli.py` (добавить команды `init`, улучшить `status`)
- Тесты: `tests/integration/test_mvp.py`
- Документация: `README.md` (обновить с примерами использования)
