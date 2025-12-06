# TS-AUDIT-007: Hygiene Audit

## References

- `src/**/*.py` — исходный код
- `tests/**/*.py` — тесты
- `requirements.txt` — production dependencies
- `requirements-dev.txt` — dev dependencies
- `pyproject.toml` — project config и dependencies
- `.env.example` — документация переменных окружения

## Context

Финальный этап аудита. AUDIT-005/006 подтвердили качество тестов.

**Цель AUDIT-007:** Навести гигиену:
1. TODO/FIXME комментарии — найти и разобрать
2. Unused imports — очистить
3. Docstrings — проверить наличие и актуальность
4. Dependencies — синхронизация requirements ↔ pyproject.toml ↔ реальные импорты
5. .env.example — все ли переменные документированы

## Steps

### Step 1: TODO/FIXME Audit

```bash
cd /Users/askold.romanov/code/Thing-Sandbox
source .venv/bin/activate

# Найти все TODO/FIXME
grep -rn "TODO\|FIXME\|XXX\|HACK" src/ tests/ --include="*.py"
```

**Для каждого найденного:**
1. Записать файл:строка и текст
2. Оценить актуальность (решено? устарело? всё ещё нужно?)
3. Рекомендация: удалить / оставить / создать issue

### Step 2: Unused Imports

```bash
# Использовать ruff для поиска unused imports
ruff check src/ tests/ --select F401
```

**F401** — unused import. Если найдены:
1. Проверить что действительно не используется
2. Удалить неиспользуемые
3. Запустить тесты для верификации

### Step 3: Docstrings Audit

Проверить наличие docstrings для публичного API:

```bash
# Модули без module docstring
for f in src/*.py src/**/*.py; do
  head -5 "$f" | grep -q '"""' || echo "Missing module docstring: $f"
done

# Публичные функции без docstring (выборочно)
grep -rn "^def [^_]" src/ | head -20
```

**Проверить:**
1. Все модули имеют module-level docstring
2. Публичные функции/классы имеют docstrings
3. Docstrings актуальны (не устарели после рефакторинга)

**Приоритет:** Фокус на `src/`, тесты могут иметь минимальные docstrings.

### Step 4: Dependencies Audit

**Шаг 4.1: Собрать все реальные импорты**

```bash
# Внешние импорты в src/
grep -rh "^import \|^from " src/ --include="*.py" | \
  grep -v "^from src\." | \
  grep -v "^from \." | \
  sort -u

# Внешние импорты в tests/
grep -rh "^import \|^from " tests/ --include="*.py" | \
  grep -v "^from src\." | \
  grep -v "^from \." | \
  sort -u
```

**Шаг 4.2: Сравнить с requirements.txt**

```bash
cat requirements.txt
cat requirements-dev.txt
```

**Шаг 4.3: Сравнить с pyproject.toml**

```bash
grep -A 20 "\[project.dependencies\]" pyproject.toml
grep -A 20 "\[project.optional-dependencies\]" pyproject.toml
```

**Проверить:**
1. Все импортируемые пакеты есть в requirements
2. Нет лишних пакетов в requirements (не импортируются)
3. requirements.txt и pyproject.toml синхронизированы
4. Версии указаны разумно (не слишком строгие, не слишком свободные)

### Step 5: .env.example Audit

```bash
cat .env.example
```

**Проверить:**
1. Все переменные из кода документированы
2. Есть описания/комментарии для каждой переменной
3. Нет лишних переменных (устаревших)

**Найти использование env vars в коде:**

```bash
grep -rn "os.environ\|os.getenv\|environ.get" src/ tests/
grep -rn "OPENAI_API_KEY\|PROJECT_ROOT" src/ tests/
```

## Testing

После всех исправлений:

```bash
cd /Users/askold.romanov/code/Thing-Sandbox
source .venv/bin/activate

# Качество кода
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/

# Тесты
pytest tests/unit/ -v --tb=short
```

## Deliverables

### Файл: `docs/tasks/TS-AUDIT-007_REPORT.md`

Структура:

```markdown
# AUDIT-007 Report: Hygiene

## Summary
[Что найдено, что исправлено]

## 1. TODO/FIXME Analysis

| File:Line | Comment | Status | Action |
|-----------|---------|--------|--------|
| src/foo.py:42 | TODO: refactor this | Outdated | Removed |

Total: X found, Y removed, Z remain (with justification)

## 2. Unused Imports

### Found by ruff
[Список F401 warnings]

### Fixed
[Что удалено]

### Verification
[ruff check после исправлений]

## 3. Docstrings

### Module Docstrings
| Module | Has Docstring | Quality |
|--------|---------------|---------|
| src/cli.py | ✅ | Good |

### Public API Docstrings
[Выборочная проверка ключевых функций]

### Missing/Outdated
[Если есть проблемы]

## 4. Dependencies

### Production (requirements.txt)
| Package | In requirements | In pyproject | Actually imported |
|---------|-----------------|--------------|-------------------|
| pydantic | ✅ | ✅ | ✅ |

### Dev (requirements-dev.txt)
[Аналогичная таблица]

### Issues
[Расхождения если есть]

### Sync Status
- requirements.txt ↔ pyproject.toml: [SYNCED/DIFFERS]

## 5. Environment Variables

### Documented in .env.example
| Variable | Documented | Used in code | Description |
|----------|------------|--------------|-------------|
| OPENAI_API_KEY | ✅ | ✅ | API key for OpenAI |

### Missing Documentation
[Если есть переменные в коде, но нет в .env.example]

## Changes Made

1. [Список изменений]

## Verification

[Вывод ruff/mypy/pytest после исправлений]
```
