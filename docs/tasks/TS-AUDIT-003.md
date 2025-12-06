# TS-AUDIT-003: Specs vs LLM Documentation Consistency

## References
- `docs/Thing' Sandbox LLM Approach v2.md` — подход к работе с LLM
- `docs/Thing' Sandbox LLM Prompting.md` — структура и содержание промптов
- `docs/specs/phase_1.md` — спека Phase 1
- `docs/specs/phase_3.md` — спека Phase 3
- `docs/specs/util_llm.md` — спека LLM Client
- `docs/specs/util_llm_adapter_openai.md` — спека OpenAI Adapter
- `docs/specs/util_prompts.md` — спека Prompt Renderer
- `src/schemas/*.schema.json` — JSON-схемы ответов LLM

## Context
Audit AUDIT-001 и AUDIT-002 закрыли пробелы в покрытии спеками и тестами.
Теперь проверяем **консистентность содержимого** — соответствуют ли спеки фаз и LLM-модулей документации по LLM.

## Steps

### 1. Phase specs vs LLM Approach

Для каждой спеки фазы (`phase_1.md`, `phase_3.md`) проверить:

- **LLM Integration** секция соответствует описанию в LLM Approach v2:
  - Правильная модель/конфиг для фазы?
  - Правильное использование response chains?
  - Правильная обработка ошибок (fallback)?
  - Batch execution описан корректно?

- **Data Flow** секция:
  - Input/Output типы соответствуют схемам?
  - PhaseResult используется правильно?

### 2. Phase specs vs LLM Prompting

Для фаз с LLM (phase_1) проверить:

- Описание промптов в спеке соответствует `LLM Prompting.md`:
  - System prompt структура?
  - User prompt структура?
  - Переменные для Jinja2?

### 3. Phase specs vs JSON Schemas

Проверить соответствие:

| Спека | Pydantic модель в коде | JSON Schema |
|-------|------------------------|-------------|
| phase_1.md | IntentionResponse | IntentionResponse.schema.json |
| (phase_2a — stub) | — | Master.schema.json |
| (phase_2b — stub) | — | NarrativeResponse.schema.json |
| phase_3.md | (no LLM) | — |
| (phase_4 — stub) | — | SummaryResponse.schema.json |

Для phase_1:
- Поля в Pydantic модели совпадают с JSON Schema?
- Описания полей актуальны?

### 4. LLM module specs vs LLM Approach

Для `util_llm.md` и `util_llm_adapter_openai.md` проверить:

- Интерфейсы соответствуют LLM Approach v2?
- Response chain management описан корректно?
- Error handling соответствует `util_llm_errors.md`?
- Retry logic, timeout, batch execution?

### 5. Prompts spec vs LLM Prompting

Для `util_prompts.md` проверить:

- Резолв промптов (sim override → default) описан?
- Jinja2 переменные документированы?
- Соответствует `LLM Prompting.md`?

## Testing
Задача аналитическая, автоматического тестирования не требуется.

## Deliverables

### Файл отчёта: `docs/tasks/TS-AUDIT-003_REPORT.md`

Формат отчёта:

```markdown
# Audit Report: Specs vs LLM Documentation

## Summary
[Краткий обзор состояния консистентности]

## Phase Specs vs LLM Approach
### phase_1.md
[Findings]
### phase_3.md
[Findings]

## Phase Specs vs LLM Prompting
[Findings]

## Phase Specs vs JSON Schemas
[Findings — таблица соответствия полей]

## LLM Module Specs vs LLM Approach
### util_llm.md
[Findings]
### util_llm_adapter_openai.md
[Findings]

## Prompts Spec vs LLM Prompting
[Findings]

## ✅ OK
[Что в порядке]

## ⚠️ Warnings
[Несоответствия, требующие внимания]

## ❌ Issues
[Критичные расхождения]

## 📋 Recommendations
[Конкретные правки для синхронизации]
```
