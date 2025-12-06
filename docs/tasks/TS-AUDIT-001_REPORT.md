# Audit Report: Project Inventory and Structure

## Summary

- **Python модулей**: 15 (без `__init__.py`)
- **Спецификаций**: 12
- **Unit-тестов**: 12 файлов
- **Integration-тестов**: 4 файла
- **JSON-схем**: 6

Общее состояние: проект развивается быстрее документации. Есть расхождения между CLAUDE.md и реальной структурой. Ряд модулей без спецификаций и тестов.

---

## Module Inventory Table

| Module | Spec exists? | Spec file | Unit tests? | Integration tests? |
|--------|--------------|-----------|-------------|-------------------|
| `cli.py` | ✅ | `core_cli.md` | ✅ `test_cli.py` | ✅ `test_skeleton.py` |
| `config.py` | ✅ | `core_config.md` | ✅ `test_config.py` | — |
| `narrators.py` | ✅ | `core_narrators.md` | ❌ | ✅ `test_skeleton.py` |
| `runner.py` | ✅ | `core_runner.md` | ❌ | ✅ `test_skeleton.py` |
| `phases/common.py` | ❌ | — | ❌ | — |
| `phases/phase1.py` | ✅ | `phase_1.md` | ✅ `test_phase1.py` | ✅ `test_phase1_integration.py` |
| `phases/phase2a.py` | ❌ | — | ❌ | ✅ `test_phases_stub.py` |
| `phases/phase2b.py` | ❌ | — | ❌ | ✅ `test_phases_stub.py` |
| `phases/phase3.py` | ✅ | `phase_3.md` | ✅ `test_phase3.py` | ✅ `test_phases_stub.py` |
| `phases/phase4.py` | ❌ | — | ❌ | ✅ `test_phases_stub.py` |
| `utils/exit_codes.py` | ✅ | `util_exit_codes.md` | ✅ `test_exit_codes.py` | — |
| `utils/llm.py` | ✅ | `util_llm.md` | ✅ `test_llm.py` | ✅ `test_llm_integration.py` |
| `utils/llm_errors.py` | ✅ | `util_llm_errors.md` | ✅ `test_llm_errors.py` | — |
| `utils/prompts.py` | ✅ | `util_prompts.md` | ✅ `test_prompts.py` | — |
| `utils/storage.py` | ✅ | `util_storage.md` | ✅ `test_storage.py` | — |
| `utils/llm_adapters/base.py` | ❌ | — | ❌ | — |
| `utils/llm_adapters/openai.py` | ✅ | `util_llm_adapter_openai.md` | ✅ `test_llm_adapter_openai.py` | ✅ `test_llm_adapter_openai_live.py` |

---

## Architecture Coverage

### Modules in Architecture but missing in code:
**None** — Architecture.md полностью соответствует текущему коду.

### Modules in code but missing in Architecture:
**None** — все модули из `src/` описаны в Architecture.md.

### ⚠️ CLAUDE.md vs Reality:

CLAUDE.md содержит устаревшую структуру:
```
# CLAUDE.md показывает:
src/
├── phase1.py
├── phase2a.py
├── phase2b.py
├── phase3.py
├── phase4.py
└── utils/
    ├── llm.py
    ├── storage.py
    └── exit_codes.py

# Реальность:
src/
├── phases/           # ← отдельная папка!
│   ├── common.py     # ← не упомянут
│   ├── phase1.py
│   ├── phase2a.py
│   ├── phase2b.py
│   ├── phase3.py
│   └── phase4.py
└── utils/
    ├── llm.py
    ├── llm_errors.py   # ← не упомянут
    ├── prompts.py      # ← не упомянут
    ├── storage.py
    ├── exit_codes.py
    └── llm_adapters/   # ← не упомянут
        ├── base.py
        └── openai.py
```

---

## Specs Coverage

### Specs without corresponding code:
**None** — все спеки имеют соответствующий код.

### Modules without specs:

| Module | Expected spec name |
|--------|-------------------|
| `phases/common.py` | `phase_common.md` |
| `phases/phase2a.py` | `phase_2a.md` |
| `phases/phase2b.py` | `phase_2b.md` |
| `phases/phase4.py` | `phase_4.md` |
| `utils/llm_adapters/base.py` | `util_llm_adapter_base.md` |

**Итого: 5 модулей без спецификаций**

---

## Tests Coverage

### Modules without unit tests:

| Module | Status |
|--------|--------|
| `runner.py` | Тестируется только через integration |
| `narrators.py` | Тестируется только через integration |
| `phases/common.py` | Нет тестов |
| `phases/phase2a.py` | Только stub-тесты |
| `phases/phase2b.py` | Только stub-тесты |
| `phases/phase4.py` | Только stub-тесты |
| `utils/llm_adapters/base.py` | Нет тестов |

**Итого: 7 модулей без выделенных unit-тестов**

### Modules without integration tests:
- `config.py`
- `utils/exit_codes.py`
- `utils/llm_errors.py`
- `utils/prompts.py`
- `utils/storage.py`
- `utils/llm_adapters/base.py`

### Test files without corresponding modules:
**None** — все тестовые файлы тестируют существующие модули.

Примечание: `test_phases_stub.py` и `test_skeleton.py` — это интеграционные тесты, которые тестируют несколько модулей вместе.

---

## JSON Schemas

### Schemas and their usage:

| Schema | Used in code? | How? |
|--------|---------------|------|
| `Character.schema.json` | ⚠️ | Только в документации |
| `Location.schema.json` | ⚠️ | Только в документации |
| `IntentionResponse.schema.json` | ⚠️ | Упомянут в docstring `phase1.py:31` |
| `Master.schema.json` | ⚠️ | Упомянут в docstring `phase2a.py:54` |
| `NarrativeResponse.schema.json` | ⚠️ | Только в документации |
| `SummaryResponse.schema.json` | ⚠️ | Только в документации |

**Вывод**: JSON-схемы **НЕ используются** в коде для валидации. Валидация идёт через Pydantic модели. Схемы существуют как документация контракта, но код их не читает.

---

## ✅ OK

1. **Architecture.md актуален** — полностью соответствует структуре кода
2. **Нет сиротских спеков** — все спецификации имеют код
3. **Нет сиротских тестов** — все тесты тестируют существующий код
4. **Core-модули покрыты** — cli, config, llm, storage имеют спеки и тесты
5. **Phase 1 и Phase 3 полностью задокументированы** — есть спеки и тесты

---

## ⚠️ Warnings

1. **CLAUDE.md устарел** — структура `src/` не соответствует реальности (phases/, utils/llm_adapters/, дополнительные файлы)

2. **5 модулей без спецификаций**:
   - `phases/common.py`
   - `phases/phase2a.py`
   - `phases/phase2b.py`
   - `phases/phase4.py`
   - `utils/llm_adapters/base.py`

3. **JSON-схемы не используются в коде** — это дублирование с Pydantic моделями или мёртвый код

4. **Фазы 2a, 2b, 4 — stubs** — тесты проверяют только stub-логику, не реальную имплементацию

---

## ❌ Issues

1. **7 модулей без выделенных unit-тестов** — нарушает правило "Every change must be covered by a unit test"

2. **runner.py и narrators.py** — критичные модули без unit-тестов (только integration)

---

## 📋 Recommendations

### Следующие шаги аудита:

1. **TS-AUDIT-002**: Обновить CLAUDE.md — синхронизировать структуру с реальностью

2. **TS-AUDIT-003**: Принять решение по JSON-схемам:
   - Вариант A: Удалить как мёртвый код
   - Вариант B: Внедрить валидацию через jsonschema
   - Вариант C: Оставить как документацию (пометить явно)

3. **TS-AUDIT-004**: Создать спецификации для модулей без спек (5 штук)

4. **TS-AUDIT-005**: Добавить unit-тесты для модулей без тестов (7 штук)

5. **TS-AUDIT-006**: Аудит содержимого спецификаций — проверить актуальность описанных интерфейсов
