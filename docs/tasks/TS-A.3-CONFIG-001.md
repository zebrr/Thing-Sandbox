# TS-CONFIG-001: Спроектировать и реализовать модуль Config

## References

- Спецификация: `docs/specs/core_config.md`
- Архитектура: `docs/Thing' Sandbox Architecture.md` (секции 4, 9)
- Существующий config: `config.toml`, `.env.example`
- Exit codes: `src/utils/exit_codes.py`

## Context

Этапы A.1 и A.2 завершены — структура проекта создана, exit codes реализованы. Теперь нужен модуль конфигурации, который будет загружать настройки из `config.toml` и секреты из `.env`.

Модуль Config — core-компонент, используемый CLI, Runner и другими модулями для доступа к настройкам приложения и резолва промптов.

### Ключевые решения

1. **Один класс Config** с вложенными Pydantic-моделями для секций
2. **Секреты из `.env`** загружаются в тот же Config
3. **Нет `config.toml`** → EXIT_CONFIG_ERROR (файл обязателен)
4. **Нет дефолтного промпта** → EXIT_INPUT_ERROR
5. **Нет промпта симуляции** → warning в лог, берём дефолтный
6. **Валидация** через Pydantic Field constraints

## Steps

### 1. Изучить спецификацию

Прочитай `docs/specs/core_config.md` — там полное описание API, примеры использования и тест-кейсы.

### 2. Проверить зависимости

Убедись, что `pydantic-settings` есть в `requirements.txt`. Если нет — добавь:
```
pydantic-settings>=2.0
```

### 3. Реализовать модуль

Создай `src/config.py`:

**Исключения:**
```python
class ConfigError(Exception):
    """Raised when configuration loading fails."""
    pass

class PromptNotFoundError(Exception):
    """Raised when required prompt file not found."""
    pass
```

**Вложенные модели:**
```python
class SimulationConfig(BaseModel):
    memory_cells: int = Field(ge=1, le=10, default=5)

class LLMConfig(BaseModel):
    # Placeholder for A.5, пока пустой
    pass
```

**Основной класс Config:**
- Наследуется от `pydantic_settings.BaseSettings` или использует композицию
- `Config.load(config_path: Path | None = None) -> Config` — classmethod для загрузки
- `config.simulation: SimulationConfig` — настройки симуляции
- `config.llm: LLMConfig` — placeholder для A.5
- `config.openai_api_key: str | None` — из `.env`
- `config.telegram_bot_token: str | None` — из `.env`
- `config.resolve_prompt(prompt_name: str, sim_path: Path | None = None) -> Path`

**Логика resolve_prompt:**
1. Если `sim_path` передан — проверить `{sim_path}/prompts/{prompt_name}.md`
2. Если override существует — вернуть его путь
3. Если override не существует — залогировать warning
4. Проверить дефолтный `src/prompts/{prompt_name}.md`
5. Если дефолтный существует — вернуть его путь
6. Если дефолтный не существует — raise PromptNotFoundError

**Определение project root:**
- Идти вверх от `__file__` пока не найдём `pyproject.toml`
- Или принять явный путь в `Config.load(config_path=...)`

### 4. Написать тесты

Создай `tests/unit/test_config.py`:

**Тест-кейсы (используй tmp_path фикстуру pytest для изоляции):**

Загрузка конфига:
- `test_load_valid_config` — успешная загрузка валидного config.toml
- `test_load_missing_config` — ConfigError если config.toml отсутствует
- `test_load_invalid_toml` — ConfigError если синтаксис TOML невалидный
- `test_load_validation_error` — ConfigError если значения не проходят валидацию (например, memory_cells=0)
- `test_default_values` — дефолтные значения применяются если секция/поле отсутствует

Загрузка .env:
- `test_env_loading` — секреты загружаются из .env
- `test_env_missing` — работает без .env, секреты = None

Резолв промптов:
- `test_resolve_prompt_default` — возвращает путь к дефолтному промпту
- `test_resolve_prompt_override` — возвращает путь к override из симуляции
- `test_resolve_prompt_missing_default` — PromptNotFoundError если дефолтного нет
- `test_resolve_prompt_missing_override_warning` — warning в лог, возвращает дефолтный

**Важно для тестов:**
- Создавай временные config.toml и .env в tmp_path
- Мокай или переопределяй project root для изоляции
- Используй `caplog` фикстуру pytest для проверки warnings

### 5. Обновить спецификацию

В `docs/specs/core_config.md` измени статус:
```
## Status: READY
```

## Testing

```bash
# Активировать venv
source venv/bin/activate

# Проверка качества кода
ruff check src/config.py
ruff format src/config.py
mypy src/config.py

# Запуск тестов
pytest tests/unit/test_config.py -v

# Проверка импорта и базовой функциональности
python -c "
from src.config import Config, ConfigError, PromptNotFoundError
print('Import OK')
"
```

**Ожидаемый результат:**
- ruff: no issues
- mypy: no errors
- pytest: all tests passed
- import: prints "Import OK"

## Deliverables

- [ ] `src/config.py` — реализация модуля
- [ ] `tests/unit/test_config.py` — юнит-тесты (10+ тест-кейсов)
- [ ] `requirements.txt` — добавить pydantic-settings если отсутствует
- [ ] `docs/specs/core_config.md` — статус обновлён на READY
- [ ] `docs/tasks/TS-CONFIG-001_REPORT.md` — отчёт о выполнении
