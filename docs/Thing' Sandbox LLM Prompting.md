# Thing' Sandbox: LLM Prompting

Концептуальный документ по формированию промптов в проекте. Описывает принципы, структуру, анти-паттерны и шаблоны для каждой фазы.

---

## 1. Обзор

### Связь с LLM Approach

Промпты — отдельный слой от транспорта. `docs/Thing' Sandbox LLM Approach v2.md` описывает как доставлять запросы (адаптеры, chains, retry). Этот документ описывает что отправлять (структура промптов, контент).

### Промпты: адаптер + симуляция

Промпты зависят от двух факторов:

| Фактор | Что определяет |
|--------|----------------|
| **Адаптер** | Базовая структура, принципы (reasoning vs traditional), ограничения модели |
| **Симуляция** | Сеттинг, тон, специфика мира, стиль персонажей |

**Дефолтные шаблоны** в этом документе — минимальные и универсальные. Конкретная симуляция должна создавать свои промпты (можно на основе шаблона), добавляя:
- Сеттинг мира
- Специфические ограничения
- Тон и стиль (эпоха, жанр)
- Особенности персонажей

Пока у нас один адаптер — OpenAI GPT-5 family. Все модели семейства — reasoning models.

### Специфика reasoning models

GPT-5 family выполняет внутренний chain-of-thought автоматически. Это требует принципиально другого подхода к промптам:

| Традиционные модели | Reasoning models (GPT-5) |
|---------------------|--------------------------|
| "Think step by step" помогает | CoT инструкции мешают |
| Few-shot улучшает качество | Примеры перегружают reasoning |
| Verbose instructions работают | Прямые, чистые инструкции лучше |

Reasoning summary берём из транспорта (OpenAI возвращает в ответе), не просим модель выводить рассуждения в output.

---

## 2. Принципы формирования промптов

### 2.1 Context Ordering

Исследования внимания LLM показывают эффект "Lost in the Middle": информация в начале (primacy) и в конце (recency) промпта получает больше внимания, середина — меньше.

**Правило размещения:**

| Позиция | Что размещать | Почему |
|---------|---------------|--------|
| **Начало** (Primacy) | Правила мира, identity, формат выхода | Критичные ограничения не потеряются |
| **Середина** | Память, история, расширенный контекст | Менее критично, можно потерять детали |
| **Конец** (Recency) | Текущая сцена, окружение, запрос | В фокусе внимания при генерации |

**Усиление критичных правил:** самые важные ограничения дублируем в начале И в конце промпта.

### 2.2 Action Boundaries

Reasoning models склонны строить многошаговые планы. Для симуляции нужно одно действие за тик.

**Явные ограничения в промпте:**
- ONE action this tick
- Do NOT plan ahead
- Do NOT describe what you "will do later"
- Choose only what happens RIGHT NOW

### 2.3 Zero-Shot Preferred

Для reasoning models примеры в промпте скорее мешают — перегружают внутренний reasoning process.

**Правило:** 0 примеров по умолчанию. Максимум 1 пример, только если без него модель систематически ошибается в формате.

### 2.4 System vs User Prompt

| System Prompt | User Prompt |
|---------------|-------------|
| Стабильное между тиками | Динамическое каждый тик |
| Роль, правила мира, формат | Текущее состояние, контекст |
| Редко меняется | Всегда разное |

**System prompt:** сеттинг симуляции, ограничения персонажа, формат выхода.

**User prompt:** identity персонажа, состояние, память, локация, окружение, запрос.

---

## 3. Анти-паттерны

### 3.1 CoT инструкции

❌ **Не делать:**
```
Think step by step about what to do.
Let's work through this carefully.
First analyze, then decide.
```

✅ **Делать:** просто задать вопрос, модель сама подумает.

### 3.2 Verification инструкции

❌ **Не делать:**
```
Double-check your answer.
Verify that your response is correct.
Make sure you considered all options.
```

Reasoning models уже делают внутреннюю верификацию. Дополнительные инструкции создают interference.

### 3.3 Множественные примеры

❌ **Не делать:**
```
Example 1: ...
Example 2: ...
Example 3: ...
Now do the same for:
```

✅ **Делать:** zero-shot или максимум один пример.

### 3.4 Многошаговые планы в output

❌ **Не делать:**
```
{
  "step1": "First I will...",
  "step2": "Then I will...",
  "step3": "Finally I will..."
}
```

✅ **Делать:** одно поле с одним действием.

### 3.5 Separate reasoning field

❌ **Don't:**
```
{
  "thinking": "I considered options A, B, C...",
  "action": "I choose B"
}
```

✅ **Do:** single field with reasoning + action together.

Reasoning models provide chain-of-thought via transport (OpenAI reasoning summary). No need for separate output field.

**Note:** This anti-pattern is about **separate fields** for thinking. Having reasoning *inside* the intention field is fine — it helps the arbiter understand character's motivation when resolving the scene.

---

## 4. Фаза 1: Формирование намерений

### 4.1 Роль

Персонаж формирует намерение — что он хочет сделать в этот тик. Намерение передаётся арбитру (Phase 2a), который разрешает сцену.

### 4.2 Выходная схема

```json
{
  "intention": "string — что персонаж намерен сделать"
}
```

Схема: `IntentionResponse.schema.json`

**Формат содержимого intention:**
- Краткое обоснование, мысли персонажа (1-3 предложения)
- Само действие (1-2 предложения)
- Всё в одном поле, не разделяем (можно поделить на абзацы)

### 4.3 Ограничения персонажа

Персонаж НЕ знает:
- Что он в симуляции
- Про тики, фазы, механику
- Internal state других персонажей
- Цели других персонажей (кроме того, что узнал из опыта)

Персонаж воспринимает:
- Только то, что явно описано в окружении
- Других персонажей через `name` + `description`
- Соседнее окружение — ограниченно
- Прошлое — через свою память

### 4.4 System Prompt — structure

```
1. SETTING
   World context — place, era, atmosphere.
   Written for specific simulation. No spoilers for character —
   they don't know the "truth" about what's happening.

2. ROLE & TASK
   You are a character in this world.
   Your task: decide what you want to do RIGHT NOW.
   
   Output structure:
   - First: your reasoning (2-3 sentences) — what you consider,
     what drives your decision
   - Then: your intended action (1-2 sentences) — what exactly
     you will do

3. CONSTRAINTS
   - You do not know you are in a simulation
   - Do NOT address any audience or narrator
   - You can ONLY perceive what is explicitly described
   - You cannot read others' thoughts or know their goals
   - ONE action this tick — do NOT plan multiple steps ahead
   - Respond in the language of the simulation content (character descriptions, locations, memories)
```

**Note:** OUTPUT FORMAT section not needed — Structured Outputs enforce format via schema.

### 4.5 User Prompt — structure

```
1. CHARACTER (identity)
   - name
   - description — personality, values, behavior patterns
   - triggers — automatic reactions

2. STATE
   - internal_state — emotions, feelings
   - external_intent — current goals, focus

3. MEMORY
   - cells — last K events (newest to oldest)
   - summary — compressed history before cells

4. LOCATION
   - name, description
   - moment — what's happening right now
   - connections — where you can go

5. PRESENT (who is here)
   - Other characters: only name + description
   - NOT their internal_state or goals
```

**Note:** No query/instruction at the end — user prompt contains only data. Task instruction is in system prompt (Role section).

### 4.6 Prompt template

**System Prompt:**

```markdown
## Setting

[Simulation-specific setting — place, era, world context.
No spoilers for character — they don't know the "truth".]

## Role

You are a character in this world.
Your task: decide what you want to do RIGHT NOW.

Use your goals, memories, and surroundings to make a decision.

Output structure:
- First: your reasoning (2-3 sentences) — what you consider, what drives your decision
- Then: your intended action (1-2 sentences) — what exactly you will do

## Constraints

- You do not know you are in a simulation
- Do NOT address any audience or narrator  
- You can ONLY perceive what is explicitly described
- You cannot read others' thoughts or know their goals
- ONE action this tick — do NOT plan multiple steps ahead
- Respond in the language of the simulation content (character descriptions, locations, memories)
```

**User Prompt:**

```markdown
## Character

**Name:** {character.identity.name}

{character.identity.description}

**Triggers:** {character.identity.triggers}

## Your State

**Internal:** {character.state.internal_state}

**Current focus:** {character.state.external_intent}

## Your Memories

**Recent:**
{for cell in character.memory.cells}
- {cell.text}
{endfor}

**Long ago:** {character.memory.summary}

## Location

**{location.identity.name}:** {location.identity.description}

**Right now:** {location.state.moment}

**Exits:**
{for conn in location.identity.connections}
- {conn.description} → {conn.location_id}
{endfor}

## Present Here

{for other in others_in_location}
- **{other.identity.name}:** {other.identity.description}
{endfor}
```

**Note:** User prompt ends with data only. Task instruction is in system prompt (Role section).

---

## 5. Фаза 2a: Разрешение сцены

*TODO — после реализации Phase 1*

---

## 6. Фаза 2b: Генерация нарратива

*TODO*

---

## 7. Фаза 4: Суммаризация памяти

*TODO*

---

## Ссылки

- Транспорт: `docs/Thing' Sandbox LLM Approach v2.md`
- Схемы: `src/schemas/`
- Концепция проекта: `docs/Thing' Sandbox Concept.md`
