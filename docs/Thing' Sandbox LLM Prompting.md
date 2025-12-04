# Thing' Sandbox: LLM Prompting

Концептуальный документ по формированию промптов в проекте. Описывает принципы, структуру и анти-паттерны. Сами шаблоны промптов находятся в `src/prompts/`.

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

**Базовые шаблоны** находятся в `src/prompts/` — минимальные и универсальные. Конкретная симуляция может создавать свои промпты (на основе базовых), добавляя:
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

## 3. Template Parameterization

### 3.1 Синтаксис

Промпты используют **Jinja2** — стандартный шаблонизатор Python.

**Базовый синтаксис:**

| Конструкция | Синтаксис | Пример |
|-------------|-----------|--------|
| Подстановка | `{{ expr }}` | `{{ character.identity.name }}` |
| Условие | `{% if %}...{% endif %}` | `{% if triggers %}...{% endif %}` |
| Цикл | `{% for %}...{% endfor %}` | `{% for c in others %}...{% endfor %}` |
| Фильтр | `{{ expr \| filter }}` | `{{ value \| default("None") }}` |

**Whitespace control:** `{%-` и `-%}` убирают пробелы/переносы вокруг тегов. Полезно для чистого вывода в списках.

### 3.2 Доступные объекты

Каждая фаза получает свой набор данных для рендеринга промпта.

#### Phase 1: Intention

| Объект | Тип | Описание |
|--------|-----|----------|
| `character` | Character | Персонаж полностью (identity, state, memory) |
| `location` | Location | Текущая локация персонажа |
| `others` | list[Character] | Другие в локации (только identity) |

#### Phase 2a: Resolution

| Объект | Тип | Описание |
|--------|-----|----------|
| `location` | Location | Локация сцены |
| `characters` | list[Character] | Персонажи в сцене (identity + state, без memory) |
| `intentions` | dict[str, str] | Намерения: `{character_id: intention_text}` |
| `tick` | int | Номер текущего тика |

#### Phase 2b: Narrative

| Объект | Тип | Описание |
|--------|-----|----------|
| `location_before` | Location | Локация ДО разрешения сцены |
| `characters_before` | list[Character] | Персонажи ДО (identity + state) |
| `intentions` | dict[str, str] | Что хотели сделать |
| `master_result` | MasterOutput | Результат разрешения сцены |

#### Phase 4: Memory

| Объект | Тип | Описание |
|--------|-----|----------|
| `character` | Character | Персонаж полностью (включая memory) |
| `tick` | int | Номер тика |

#### Глобально доступно

| Объект | Тип | Описание |
|--------|-----|----------|
| `simulation.id` | str | Идентификатор симуляции |
| `simulation.current_tick` | int | Текущий тик симуляции |

### 3.3 Паттерны для пустых значений

**Осмысленный default вместо "—":**

```jinja2
**Your habits:** {{ character.identity.triggers | default("You have no specific behavior patterns.") }}
```

**Скрытие секции если пусто:**

```jinja2
{% if character.identity.triggers %}
**Triggers:** {{ character.identity.triggers }}
{% endif %}
```

### 3.4 Паттерны для списков

**Плейсхолдер для пустого списка:**

```jinja2
## Present Here
{% if others %}
{% for other in others -%}
- **{{ other.identity.name }}:** {{ other.identity.description }}
{% endfor %}
{% else %}
You are alone here.
{% endif %}
```

**Скрытие секции если список пуст:**

```jinja2
{% if others %}
## Present Here
{% for other in others -%}
- **{{ other.identity.name }}:** {{ other.identity.description }}
{% endfor %}
{% endif %}
```

### 3.5 Доступ к вложенным структурам

**Поля объекта:**

```jinja2
{{ character.identity.name }}
{{ character.state.internal_state }}
{{ location.state.moment }}
```

**Элементы словаря (intentions):**

```jinja2
{% for char_id, intention in intentions.items() %}
**{{ char_id }}:** {{ intention }}
{% endfor %}
```

**Память персонажа:**

```jinja2
{% for cell in character.memory.cells %}
- {{ cell.text }}
{% endfor %}

**Long ago:** {{ character.memory.summary | default("You don't remember anything from long ago.") }}
```

**Connections локации:**

```jinja2
{% for conn in location.identity.connections %}
- {{ conn.description }} → {{ conn.location_id }}
{% endfor %}
```

---

## 4. Анти-паттерны

### 4.1 CoT инструкции

❌ **Не делать:**
```
Think step by step about what to do.
Let's work through this carefully.
First analyze, then decide.
```

✅ **Делать:** просто задать вопрос, модель сама подумает.

### 4.2 Verification инструкции

❌ **Не делать:**
```
Double-check your answer.
Verify that your response is correct.
Make sure you considered all options.
```

Reasoning models уже делают внутреннюю верификацию. Дополнительные инструкции создают interference.

### 4.3 Множественные примеры

❌ **Не делать:**
```
Example 1: ...
Example 2: ...
Example 3: ...
Now do the same for:
```

✅ **Делать:** zero-shot или максимум один пример.

### 4.4 Многошаговые планы в output

❌ **Не делать:**
```
{
  "step1": "First I will...",
  "step2": "Then I will...",
  "step3": "Finally I will..."
}
```

✅ **Делать:** одно поле с одним действием.

### 4.5 Separate reasoning field

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

## 5. Фаза 1: Формирование намерений

### 5.1 Роль

Персонаж формирует намерение — что он хочет сделать в этот тик. Намерение передаётся арбитру (Phase 2a), который разрешает сцену.

### 5.2 Входные и выходные данные

**Вход:** см. секцию 3.2 (Phase 1: Intention)

**Выход:** `src/schemas/IntentionResponse.schema.json`

**Формат содержимого intention:**
- Краткое обоснование, мысли персонажа (1-3 предложения)
- Само действие (1-2 предложения)
- Всё в одном поле, не разделяем (можно поделить на абзацы)

### 5.3 Ограничения персонажа

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

### 5.4 System Prompt — structure

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

### 5.5 User Prompt — structure

```
1. CHARACTER (identity)
   - name — from character's perspective ("Your name")
   - description — personality, values, behavior patterns
   - triggers — automatic reactions ("Your habits")

2. STATE
   - internal_state — emotions, feelings ("How you feel")
   - external_intent — current goals, focus ("What you want")

3. MEMORY
   - cells — last K events (newest first, oldest last — order implies recency)
   - summary — compressed history before cells

4. LOCATION
   - name, description
   - moment — what's happening right now
   - connections — where you can go ("You can go")

5. PRESENT (who is here)
   - Other characters: only name + description
   - NOT their internal_state or goals
```

**Note:** No query/instruction at the end — user prompt contains only data. Task instruction is in system prompt (Role section).

### 5.6 Prompt templates

См. файлы:
- `src/prompts/phase1_intention_system.md`
- `src/prompts/phase1_intention_user.md`

---

## 6. Фаза 2a: Разрешение сцены

### 6.1 Роль

Арбитр (Game Master) разрешает сцену в локации — определяет что произошло, обновляет состояния персонажей и локации.

### 6.2 Входные и выходные данные

**Вход:** см. секцию 3.2 (Phase 2a: Resolution)

**Выход:** `src/schemas/Master.schema.json`

### 6.3 Ограничения арбитра

Арбитр ДОЛЖЕН:
- Разрешить все намерения персонажей (успех, частичный успех, неудача)
- Учитывать триггеры персонажей при разрешении
- Писать `memory_entry` от первого лица персонажа, субъективно
- Обновлять `moment` локации даже если ничего особенного не произошло

Арбитр НЕ ДОЛЖЕН:
- Убивать персонажей без веской причины
- Игнорировать намерения персонажей
- Нарушать логику мира и характеров
- Планировать за пределами текущего тика

**Пустые локации:** если персонажей нет, арбитр обновляет только `location.moment` (мир живёт).

### 6.4 System Prompt — structure

```
1. SETTING
   Full world context — the arbiter knows everything about the world,
   including hidden mechanics, secrets, and "the truth" that characters
   don't know. Written for specific simulation.

2. ROLE & TASK
   You are the Game Master of this world.
   Your task: resolve the scene — determine what happens based on
   character intentions, their personalities, and circumstances.

3. RULES
   - Resolve each intention: success, partial success, or failure
   - Consider character triggers and personalities
   - Write memory_entry from each character's subjective perspective
   - Update location moment to reflect current state
   - If location is empty — just update the moment (world lives on)

4. CONSTRAINTS
   - Do NOT kill characters without strong reason
   - Do NOT ignore any character's intention
   - Stay within THIS tick — no future planning
   - Respect character personalities and world logic
   - Respond in the language of the simulation content (character descriptions, locations, memories)
```

### 6.5 User Prompt — structure

```
1. LOCATION
   - identity (id, name, description, connections)
   - state (moment)

2. CHARACTERS (for each)
   - identity (id, name, description, triggers)
   - state (internal_state, external_intent)

3. INTENTIONS
   - character_id: intention text

4. TICK
   - Current tick number
```

### 6.6 Prompt templates

См. файлы:
- `src/prompts/phase2a_resolution_system.md`
- `src/prompts/phase2a_resolution_user.md`

---

## 7. Фаза 2b: Генерация нарратива

### 7.1 Роль

Нарратор описывает сцену для наблюдателя — что произошло в локации за этот тик. Рассказ от третьего лица, художественный стиль.

### 7.2 Входные и выходные данные

**Вход:** см. секцию 3.2 (Phase 2b: Narrative)

**Выход:** `src/schemas/NarrativeResponse.schema.json`

### 7.3 Ограничения нарратора

Нарратор ДОЛЖЕН:
- Описывать действия и события, не статичные состояния
- Показывать что персонажи *делали*, а не где они *находятся*
- Отражать разницу между намерением и результатом (если есть)
- Упоминать изменения локации
- Для пустых локаций — описывать жизнь мира (природа, время, атмосфера)

Нарратор НЕ ДОЛЖЕН:
- Раскрывать внутренние мысли персонажей напрямую
- Описывать то, что не произошло в этом тике
- Спойлерить будущее
- Обращаться к читателю

### 7.4 System Prompt — structure

```
1. SETTING
   Full world context — the narrator knows everything about the world.
   Unlike the arbiter, the narrator chooses what to reveal to the reader:
   can hint, build suspense, but not spoil what characters don't know yet.

2. CONTEXT
   The simulation is run by a Game Master (arbiter) who resolves all
   character actions and determines outcomes. Narrator receives the
   Game Master's decisions and turns them into a story.

3. ROLE & TASK
   You are the Narrator of this world.
   Your task: describe what happened in this scene as a story.
   Write in third person, show actions and events.

4. STYLE
   - Literary, evocative prose
   - Show, don't tell
   - Focus on what changed, not static descriptions
   - For empty locations — describe the world living on

5. CONSTRAINTS
   - Do NOT reveal characters' inner thoughts directly
   - Do NOT describe events outside this tick
   - Do NOT address the reader
   - Respond in the language of the simulation content (character descriptions, locations, memories)
```

### 7.5 User Prompt — structure

```
1. LOCATION
   - name, description
   - moment before the scene
   - moment after Game Master's resolution
   - description change (if any)

2. CHARACTERS (for each)
   - name, description
   - state before (internal_state, external_intent)
   - intention — what character wanted to do
   - state after Game Master's resolution
   - movement (if changed location)

3. EMPTY LOCATION
   - If no characters — just location before/after
```

### 7.6 Prompt templates

См. файлы:
- `src/prompts/phase2b_narrative_system.md`
- `src/prompts/phase2b_narrative_user.md`

---

## 8. Фаза 4: Суммаризация памяти

### 8.1 Роль

Суммаризатор сжимает память персонажа — объединяет текущий `summary` с выпадающей ячейкой в новый `summary`. Память субъективна, от первого лица.

### 8.2 Входные и выходные данные

**Вход:** см. секцию 3.2 (Phase 4: Memory)

**Выход:** `src/schemas/SummaryResponse.schema.json`

### 8.3 Ограничения суммаризатора

Суммаризатор ДОЛЖЕН:
- Писать от первого лица персонажа
- Сохранять значимые события (открытия, конфликты, встречи, потери)
- Сохранять отношения с другими персонажами
- Сохранять ключевые решения и их последствия
- Сохранять сильные эмоциональные переживания
- Держать объём в пределах 2-3 абзацев

Суммаризатор МОЖЕТ забывать:
- Повседневные действия без последствий
- Незначительные детали обстановки
- Переходы между локациями без событий
- Мелкие диалоги ни о чём
- Рутину ("ждал", "ничего не происходило")

Суммаризатор НЕ ДОЛЖЕН:
- Добавлять то, чего не было в памяти
- Писать от третьего лица
- Раскрывать то, что персонаж не знает

### 8.4 System Prompt — structure

```
1. SETTING
   World context — same as character's view (limited knowledge).
   The character doesn't know "the truth" about the world.

2. ROLE & TASK
   You compress the character's memory.
   Merge the old summary with the dropping memory cell into a new summary.
   Write from the character's first-person perspective.

3. PRIORITIES
   Remember: significant events, relationships, decisions, emotions
   Forget: routine, trivial details, uneventful moments

4. CONSTRAINTS
   - First person perspective
   - Do NOT add events that didn't happen
   - Do NOT reveal what the character doesn't know
   - Keep to 2-3 paragraphs
   - Respond in the language of the simulation content (character descriptions, locations, memories)
```

### 8.5 User Prompt — structure

```
1. CHARACTER
   - name, description (for voice/perspective)

2. OLD SUMMARY
   - Current compressed history

3. DROPPING CELL
   - Memory being pushed out of detailed cells

4. TICK
   - Current tick number (for context)
```

### 8.6 Prompt templates

См. файлы:
- `src/prompts/phase4_summary_system.md`
- `src/prompts/phase4_summary_user.md`

---

## Ссылки

- Базовые шаблоны промптов: `src/prompts/`
- Транспорт: `docs/Thing' Sandbox LLM Approach v2.md`
- Схемы: `src/schemas/`
- Концепция проекта: `docs/Thing' Sandbox Concept.md`
