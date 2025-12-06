# TS-AUDIT-005: Code vs Tests Audit

## References

- `docs/specs/*.md` — все спецификации модулей (секции "Public API" и "Test Coverage")
- `tests/unit/*.py` — unit-тесты
- `tests/integration/*.py` — интеграционные тесты
- `src/**/*.py` — исходный код

## Context

Продолжаем аудит проекта. Предыдущие этапы (001-004a) построили карту проекта, создали недостающие спеки и тесты, проверили консистентность документации, отрефакторили logging.

**Текущий статус:** 349 тестов, 15 спек, 15 модулей.

**Цель AUDIT-005:** Проверить качество тестового покрытия:
1. Покрыт ли весь публичный API тестами
2. Содержат ли тесты осмысленные assertions (не просто "код не падает")
3. Соответствуют ли реальные тесты описанным в спеках

## Steps

### Step 1: Построить матрицу покрытия

Для каждого модуля из `src/`:

1. Извлечь публичный API из спеки (секция "Public API")
2. Найти соответствующий тест-файл в `tests/unit/`
3. Сопоставить: функция/класс/метод → тест(ы)

**Формат записи:**
```
## module_name (src/path/module.py)

### Public API (из спеки)
- function_one() — ✅ test_function_one_basic, test_function_one_edge_case
- function_two() — ❌ НЕТ ТЕСТОВ
- ClassName.method() — ⚠️ частичное покрытие (только happy path)
```

### Step 2: Проверить качество assertions

Для каждого тест-файла проверить:

1. **Есть ли assertions?** — тесты без assert бесполезны
2. **Что проверяется?** — результат, side effects, exceptions, типы
3. **Достаточно ли проверок?** — один assert на весь тест — подозрительно

**Красные флаги:**
- `assert result` без проверки конкретного значения
- Только `assert not raises` без проверки результата
- Тест создаёт объект, но не проверяет его состояние

### Step 3: Сверить тесты со спеками

Для каждой спеки с секцией "Test Coverage":

1. Открыть спеку, найти список тестов
2. Проверить, что все перечисленные тесты существуют
3. Проверить, что тесты делают то, что описано

**Фиксировать:**
- Тесты в спеке, но нет в коде
- Тесты в коде, но нет в спеке
- Тест существует, но проверяет другое

### Step 4: Проверить integration tests

Для `tests/integration/`:

1. Какие модули покрыты интеграционными тестами
2. Есть ли правильные markers (`@pytest.mark.integration`, `@pytest.mark.slow`)
3. Есть ли skip conditions для внешних зависимостей (API keys)

## Testing

После анализа — убедиться, что все тесты проходят:

```bash
cd /Users/askold.romanov/code/Thing-Sandbox
source .venv/bin/activate
pytest tests/unit/ -v --tb=short
```

Проверки качества кода НЕ требуются (это аудит, не изменение кода).

## Deliverables

### Файл: `docs/tasks/TS-AUDIT-005_REPORT.md`

Структура отчёта:

```markdown
# AUDIT-005 Report: Code vs Tests

## Executive Summary
[Общая статистика: модулей, тестов, % покрытия API, критические проблемы]

## Detailed Analysis

### module_name (src/path/module.py ↔ tests/unit/test_module.py)

**Public API Coverage:**
| API Element | Tests | Status | Notes |
|-------------|-------|--------|-------|
| func() | test_func_* | ✅ | |
| Class.method() | — | ❌ | Нет тестов |

**Assertion Quality:**
- [Оценка: хорошо / есть проблемы]
- [Конкретные проблемы если есть]

**Spec Consistency:**
- [Тесты из спеки: все есть / расхождения]

[Повторить для каждого модуля]

### Integration Tests

[Анализ integration тестов]

## Issues Found

### Critical (нет тестов для публичного API)
1. ...

### Medium (слабые assertions)
1. ...

### Low (расхождения спека/тесты)
1. ...

## Recommendations

[Что исправить в следующем этапе]
```

## Notes

- Это аудит — код НЕ менять
- Если находишь баги в тестах (тест проходит, но проверяет не то) — фиксируй в отчёте
- Спеки без секции "Test Coverage" — отметить как gap
- Фокус на unit-тестах, integration — обзорно
