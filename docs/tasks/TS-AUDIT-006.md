# TS-AUDIT-006: Test Consistency Audit

## References

- `tests/unit/*.py` — unit-тесты
- `tests/integration/*.py` — интеграционные тесты
- `tests/conftest.py` — shared fixtures
- `pytest.ini` или `pyproject.toml` — конфигурация pytest

## Context

Продолжаем аудит проекта. AUDIT-005 подтвердил хорошее покрытие (381 тест).

**Цель AUDIT-006:** Проверить консистентность тестов:
1. Markers — единообразное использование
2. Mocks — единый подход
3. tmp_path — использование для временных файлов
4. Naming conventions
5. Изоляция тестов

**Особое внимание:** `test_skeleton.py` — лежит в `integration/`, но не имеет маркера `@pytest.mark.integration`. Нужно исправить.

## Steps

### Step 1: Markers Audit

Проверить использование pytest markers:

```bash
# Найти все маркеры в тестах
grep -rn "@pytest.mark" tests/
```

**Ожидаемые маркеры:**
- `@pytest.mark.asyncio` — для async тестов
- `@pytest.mark.integration` — для integration тестов
- `@pytest.mark.slow` — для медленных тестов

**Проверить:**
1. Все файлы в `tests/integration/` имеют `@pytest.mark.integration`
2. Все async def тесты имеют `@pytest.mark.asyncio`
3. Тесты с реальными API вызовами имеют `@pytest.mark.slow`

**ИСПРАВИТЬ:** `test_skeleton.py` — добавить `@pytest.mark.integration` ко всем тестам (или на уровне модуля через `pytestmark`).

### Step 2: Mocks Consistency

Проверить подходы к мокированию:

```bash
# Найти все моки
grep -rn "MagicMock\|AsyncMock\|patch\|monkeypatch" tests/
```

**Проверить единообразие:**
- `unittest.mock.patch` vs `pytest.monkeypatch` — когда какой
- `MagicMock` vs `AsyncMock` — правильный выбор для async
- Место патчинга — где импортируется, не где определяется

**Записать паттерны:**
- Какой подход используется чаще
- Есть ли смешение стилей в одном файле

### Step 3: tmp_path Usage

Проверить работу с временными файлами:

```bash
# Найти использование tmp_path
grep -rn "tmp_path" tests/

# Найти потенциальные проблемы — запись в рабочие папки
grep -rn "simulations/" tests/ | grep -v "tmp_path"
```

**Проверить:**
1. Тесты используют `tmp_path` fixture для временных файлов
2. Нет записи в `simulations/` или `src/` напрямую
3. Нет hardcoded путей к проекту

### Step 4: Naming Conventions

Проверить единообразие именования:

**Файлы:**
- Паттерн: `test_<module>.py`
- Все ли следуют?

**Классы (если есть):**
- Паттерн: `TestClassName`

**Функции:**
- Паттерн: `test_<what>_<expected_behavior>`
- Примеры хороших: `test_load_missing_file_raises_error`
- Примеры плохих: `test_1`, `test_it_works`

```bash
# Список всех тест-функций
grep -rn "def test_" tests/ | cut -d: -f3 | sort
```

### Step 5: Test Isolation

Проверить изоляцию тестов:

**Потенциальные проблемы:**
1. Глобальное состояние между тестами
2. Зависимость от порядка выполнения
3. Shared mutable fixtures

```bash
# Проверить scope fixtures
grep -rn "@pytest.fixture" tests/ | grep "scope="
```

**Проверить:**
- Fixtures с `scope="session"` или `scope="module"` — безопасны ли?
- Нет ли изменения глобальных переменных без восстановления

## Fixes to Apply

### Fix 1: test_skeleton.py markers

Добавить маркер на уровне модуля:

```python
# В начале файла после импортов
pytestmark = pytest.mark.integration
```

Это пометит ВСЕ тесты в файле как integration.

### Fix 2: Другие найденные проблемы

Исправить по ходу аудита, документировать в отчёте.

## Testing

После исправлений:

```bash
cd /Users/askold.romanov/code/Thing-Sandbox
source .venv/bin/activate

# Проверить что skeleton тесты теперь пропускаются
pytest tests/ -m "not integration" --collect-only | grep skeleton
# Ожидание: ничего не найдено

# Проверить что они запускаются с integration
pytest tests/integration/test_skeleton.py -v --tb=short
# Ожидание: все проходят

# Полный прогон
pytest tests/ -v --tb=short
```

## Deliverables

### Файл: `docs/tasks/TS-AUDIT-006_REPORT.md`

Структура:

```markdown
# AUDIT-006 Report: Test Consistency

## Summary
[Краткая сводка: что проверено, что исправлено]

## 1. Markers Analysis

### Current Usage
[Таблица: файл | asyncio | integration | slow]

### Issues Found
- test_skeleton.py: missing @pytest.mark.integration → FIXED

### After Fix
[Подтверждение что pytest -m "not integration" работает корректно]

## 2. Mocks Analysis

### Patterns Used
[Какие подходы используются]

### Consistency
[Единообразно ли]

### Recommendations
[Если есть]

## 3. tmp_path Usage

### Good Practices
[Примеры правильного использования]

### Issues
[Если есть запись в рабочие папки]

## 4. Naming Conventions

### File Naming
[Соответствует ли паттерну]

### Function Naming
[Примеры хороших/плохих]

### Recommendations
[Если есть]

## 5. Test Isolation

### Fixture Scopes
[Какие scope используются]

### Potential Issues
[Если есть]

## Changes Made

1. test_skeleton.py: added `pytestmark = pytest.mark.integration`
2. [Другие изменения]

## Verification

[Вывод pytest --collect-only подтверждающий исправления]
```
