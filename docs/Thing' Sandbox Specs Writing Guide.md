# Thing' Sandbox: Specs Writing Guide

Все спеки создаются на английском языке в UTF-8.

## Назначение

Технические спеки — единый источник правды о реализации модулей. Они экономят контекст диалога с Claude Code, ускоряют понимание кода и служат справочником для разработки.

Спека должна полностью заменить необходимость читать исходный код для понимания возможностей модуля.

## Принципы

1. **Полнота** — вся информация для использования модуля без чтения кода
2. **Практичность** — примеры использования, частые сценарии, граничные случаи
3. **Структурированность** — единообразная структура для быстрой навигации
4. **Актуальность** — спека обновляется вместе с кодом
5. **Без украшений** — технический стиль без эмодзи и лишних слов

---

## Классификация и именование

Спецификации хранятся в `docs/specs/`. Префикс отражает тип модуля:

| Тип | Модули | Префикс спеки | Пример |
|-----|--------|---------------|--------|
| **Phase** | `phase_*.py` | `phase_` | `phase_1.py` → `phase_1.md` |
| **Core** | `cli.py`, `config.py`, `runner.py`, `narrators.py` | `core_` | `runner.py` → `core_runner.md` |
| **Utils** | `utils/*.py` | `util_` | `utils/llm.py` → `util_llm.md` |

---

## Базовая структура спеки

### 1. Заголовок и статус

```markdown
# prefix_module_name.md

## Status: READY | IN_PROGRESS | NOT_STARTED

Краткое описание назначения модуля (1-3 предложения).
```

### 2. Обязательные разделы для всех модулей

#### Public API

Полное описание публичного интерфейса:

```markdown
## Public API

### function_name(param1: Type, param2: Type = default) -> ReturnType
Описание функции.
- **Input**: 
  - param1 — описание параметра
  - param2 — описание с указанием default значения
- **Returns**: описание возвращаемого значения
- **Raises**: ExceptionType — условия возникновения

### ClassName
Описание класса и его назначения.

#### ClassName.__init__(params) -> None
Конструктор класса.
- **Input**: детальное описание параметров
- **Attributes**: список создаваемых атрибутов

#### ClassName.method(params) -> ReturnType
Описание метода.
```

#### Dependencies

```markdown
## Dependencies

- **Standard Library**: os, sys, json, pathlib
- **External**: openai>=1.0.0, pydantic>=2.0
- **Internal**: utils.storage, utils.exit_codes (или None)
```

#### Test Coverage

```markdown
## Test Coverage

- **test_module_name**: X tests
  - test_function_basic
  - test_function_edge_cases
  - test_error_handling
```

#### Usage Examples

```markdown
## Usage Examples

### Basic Usage
```python
from src.module import function

result = function(data)
```

### Error Handling
```python
try:
    result = operation()
except SpecificError as e:
    handle_error(e)
```

---

## Дополнительные разделы по типам модулей

### Phase модули (phase_*.md)

Фазы такта имеют специфические разделы:

#### Data Flow

```markdown
## Data Flow

### Input
- **characters**: List[Character] — персонажи в локации
- **location**: Location — текущая локация
- **context**: TickContext — контекст такта

### Output
- **IntentionResponse** — намерение персонажа (см. схему)

### Validation
- Input: валидация по Character.schema.json
- Output: валидация по IntentionResponse.schema.json
```

#### LLM Integration (опционально)

```markdown
## LLM Integration

- **Prompt**: `src/prompts/phase1_intention.md` (с override в симуляции)
- **Schema**: `IntentionResponse.schema.json`
- **Error handling**: retry 3 раза, затем EXIT_RUNTIME_ERROR
```

### Core модули (core_*.md)

Стандартная структура + специфика модуля:

- **core_cli.md**: CLI Interface, Commands
- **core_config.md**: Configuration sections, Validation rules
- **core_runner.md**: Tick orchestration, Atomicity guarantees
- **core_narrators.md**: Output formats, Channel configuration

### Utils модули (util_*.md)

Стандартная структура. Для сложных модулей добавлять:

#### Internal Methods (если критичны для понимания)

```markdown
## Internal Methods

### _retry_with_backoff(func, max_retries: int) -> Result
- **Purpose**: повторные попытки с экспоненциальной задержкой
- **Algorithm**: начинает с 1 сек, удваивает до max 32 сек
- **Side effects**: логирует каждую попытку
```

#### Performance Notes (если релевантно)

```markdown
## Performance Notes

- **Bottlenecks**: API rate limits (60 RPM)
- **Optimization**: batch requests where possible
```

---

## Дополнительные разделы (по необходимости)

### Configuration

```markdown
## Configuration

Section `[module]` in config.toml:

### Required Parameters
- **param_name** (type, constraints) — описание

### Optional Parameters  
- **timeout** (int, >0, default=30) — таймаут в секундах
```

### Terminal Output

> Placeholder: формат будет определён при реализации CLI

```markdown
## Terminal Output

### Output Format
TBD

### Progress Messages
TBD

### Error Messages
TBD
```

### Error Handling

```markdown
## Error Handling

### Exit Codes
Использует стандартные коды из `utils/exit_codes.py`:
- EXIT_SUCCESS (0)
- EXIT_CONFIG_ERROR (1)
- EXIT_INPUT_ERROR (2)
- EXIT_RUNTIME_ERROR (3)
- EXIT_API_LIMIT_ERROR (4)
- EXIT_IO_ERROR (5)

### Boundary Cases
- Пустой список персонажей → пропуск фазы
- LLM timeout → retry с backoff
- Невалидный JSON от LLM → retry, затем EXIT_RUNTIME_ERROR
```

---

## Требования к оформлению

### Язык и стиль

- Технический английский
- Настоящее время для описаний
- Краткие, но полные предложения
- Активный залог где возможно

### Форматирование

- **Bold** для важных терминов и названий параметров
- `code` для значений, имен функций, параметров
- ```python для блоков кода```
- Таблицы для структурированных данных

### Описания API

```markdown
### function_name(param1: Type, param2: Optional[Type] = None) -> ReturnType
Краткое описание (1-2 предложения).
- **Input**: 
  - param1 (Type) — описание
  - param2 (Optional[Type]) — описание, default: None
- **Returns**: ReturnType — что возвращает
- **Raises**: 
  - ValueError — когда возникает
  - APIError — условия
- **Side effects**: изменения состояния (если есть)
- **Note**: важные замечания
```

---

## Алгоритм создания спеки

### 1. Анализ кода
- Изучить основной файл модуля
- Выявить публичное API
- Понять основные алгоритмы
- Найти граничные случаи

### 2. Анализ тестов
- Понять сценарии использования
- Выявить граничные случаи
- Подсчитать покрытие

### 3. Анализ зависимостей
- От каких модулей зависит
- Какие модули от него зависят
- Внешние библиотеки

### 4. Структурирование
- Выбрать нужные разделы по типу модуля
- Расположить в правильном порядке
- Добавить специфичные разделы

### 5. Написание
- Начать с краткого описания
- Детально описать API
- Добавить примеры использования
- Проверить полноту

### 6. Валидация
- Можно ли использовать модуль только по спеке?
- Все ли граничные случаи описаны?
- Актуальны ли примеры?

---

## Контроль качества

### Хорошая спека

- Можно использовать модуль без чтения кода
- Понятна архитектура и основные решения
- Есть примеры для всех основных сценариев
- Описаны граничные случаи и ошибки
- Ясно, какие параметры конфигурации нужны
- Для Phase модулей: понятен Data Flow

### Плохая спека

- Требуется смотреть в код для понимания
- Нет примеров или они не работают
- Пропущены важные методы или параметры
- Не описаны типичные ошибки
- Дублирует код вместо объяснения концепций

---

## Поддержка актуальности

1. **При изменении кода** — сразу обновлять спеку
2. **При добавлении функций** — дополнять соответствующие разделы
3. **При исправлении багов** — обновлять граничные случаи
4. **При рефакторинге** — проверять актуальность описаний
