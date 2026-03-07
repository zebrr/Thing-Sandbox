# Схема потоков данных Thing' Sandbox

## Обзор данных

**Character** (персонаж):
```
identity: {id, name, description, triggers}            ← статика
state:    {location, internal_state, external_intent}  ← динамика
memory:   {cells[{tick, text}], summary}               ← субъективная история
```

**Location** (локация):
```
identity: {id, name, description, connections[{location_id, description}]}  ← статика
state:    {moment}                                                          ← динамика (что прямо сейчас)
```

---

## Схема потока по фазам

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              PHASE 1: INTENTION (N запросов)                    │
│                                                                                 │
│  SYSTEM PROMPT                     USER PROMPT                                  │
│  ┌────────────────────────┐        ┌─────────────────────────────────────────┐  │
│  │ • Setting (limited)    │        │ CHARACTER                               │  │
│  │   [мир глазами char]   │        │ • identity.name                         │  │
│  │ • Role                 │        │ • identity.description                  │  │
│  │ • Constraints          │        │ • identity.triggers                     │  │
│  └────────────────────────┘        │ STATE                                   │  │
│                                    │ • state.internal_state                  │  │
│                                    │ • state.external_intent                 │  │
│                                    │ MEMORY                                  │  │
│                                    │ • memory.cells[].text (newest first)    │  │
│                                    │ • memory.summary                        │  │
│                                    │ LOCATION (where char is)                │  │
│                                    │ • location.identity.name, description   │  │
│                                    │ • location.state.moment                 │  │
│                                    │ • location.identity.connections[]       │  │
│                                    │ OTHERS (same location, identity only)   │  │
│                                    │ • other.identity.name, description      │  │
│                                    └─────────────────────────────────────────┘  │
│                                                                                 │
│                           OUTPUT: IntentionResponse {intention}                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             PHASE 2a: RESOLUTION (L запросов)                   │
│                                                                                 │
│  SYSTEM PROMPT                     USER PROMPT                                  │
│  ┌────────────────────────┐        ┌─────────────────────────────────────────┐  │
│  │ • Setting (FULL!)      │        │ LOCATION                                │  │
│  │   [правда о мире,      │        │ • location.identity.* (id, name, desc)  │  │
│  │    скрытые механики]   │        │ • location.state.moment                 │  │
│  │ • Role (Game Master)   │        │ • location.identity.connections[]       │  │
│  │ • Rules                │        │ • [valid location IDs list]             │  │
│  │ • Constraints          │        │ CHARACTERS (in this location)           │  │
│  └────────────────────────┘        │ • char.identity.* (id, name, desc, trig)│  │
│                                    │ • char.state.internal_state             │  │
│                                    │ • char.state.external_intent            │  │
│                                    │ • **НЕТ** memory!                       │  │
│                                    │ INTENTIONS                              │  │
│                                    │ • {char_id: intention} dict             │  │
│                                    │ TICK                                    │  │
│                                    │ • simulation.current_tick               │  │
│                                    └─────────────────────────────────────────┘  │
│                                                                                 │
│                 OUTPUT: MasterOutput                                            │
│                 ┌───────────────────────────────────────────────┐               │
│                 │ tick, location_id                             │               │
│                 │ characters: {                                 │               │
│                 │   char_id: {                                  │               │
│                 │     location,          ← может измениться     │               │
│                 │     internal_state,    ← новое состояние      │               │
│                 │     external_intent,   ← новые цели           │               │
│                 │     memory_entry       ← НОВАЯ ЗАПИСЬ ПАМЯТИ  │               │
│                 │   }                                           │               │
│                 │ }                                             │               │
│                 │ location: {                                   │               │
│                 │   moment,               ← что сейчас          │               │
│                 │   description (null if unchanged)             │               │
│                 │ }                                             │               │
│                 └───────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             PHASE 2b: NARRATIVE (L запросов)                    │
│                                                                                 │
│  SYSTEM PROMPT                   USER PROMPT                                    │
│  ┌────────────────────────┐      ┌───────────────────────────────────────────┐  │
│  │ • Setting (атмосфера,  │      │ LOCATION                                  │  │
│  │   стиль, жанр)         │      │ • location_before.identity.name, desc     │  │
│  │ • Context              │      │ • location_before.state.moment            │  │
│  │ • Role (Narrator)      │      │ • master_result.location.moment (after)   │  │
│  │ • Style                │      │ • master_result.location.description      │  │
│  │ • Constraints          │      │ CHARACTERS (for each)                     │  │
│  └────────────────────────┘      │ • char_before.identity.* (name,desc,trig) │  │
│                                  │ • char_before.state.* (internal,external) │  │
│                                  │ • intentions[char_id] (что хотел)         │  │
│                                  │ • master_result.characters[char_id].*     │  │
│                                  │   (internal_state, external_intent AFTER) │  │
│                                  │ • movement info (if location changed)     │  │
│                                  └───────────────────────────────────────────┘  │
│                                                                                 │
│                       OUTPUT: NarrativeResponse {narrative}                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 3: APPLICATION (0 LLM запросов)                    │
│                                                                                 │
│  Применяем изменения из MasterOutput:                                           │
│                                                                                 │
│  Character.state.location        ← master.characters[id].location               │
│  Character.state.internal_state  ← master.characters[id].internal_state         │
│  Character.state.external_intent ← master.characters[id].external_intent        │
│  Character.memory.cells          ← PREPEND {tick, memory_entry} to cells[0]     │
│                                                                                 │
│  Location.state.moment           ← master.location.moment                       │
│  Location.identity.description   ← master.location.description (if not null)    │
│                                                                                 │
│  memory.cells сдвигается, oldest cell готовится к выпадению                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             PHASE 4: SUMMARY (N запросов)                       │
│                           (только если cells overflow)                          │
│                                                                                 │
│  SYSTEM PROMPT                     USER PROMPT                                  │
│  ┌────────────────────────┐        ┌─────────────────────────────────────────┐  │
│  │ • Setting (limited)    │        │ CHARACTER                               │  │
│  │   [как в Phase 1]      │        │ • identity.name                         │  │
│  │ • Role (compressor)    │        │ • identity.description                  │  │
│  │ • Priorities           │        │ OLD SUMMARY                             │  │
│  │ • Constraints          │        │ • memory.summary                        │  │
│  └────────────────────────┘        │ DROPPING MEMORY                         │  │
│                                    │ • memory.cells[-1].text (oldest cell)   │  │
│                                    │ TICK                                    │  │
│                                    │ • simulation.current_tick               │  │
│                                    └─────────────────────────────────────────┘  │
│                                                                                 │
│                        OUTPUT: SummaryResponse {summary}                        │
│                                                                                 │
│  После: Character.memory.summary ← new summary                                  │
│         Character.memory.cells   ← remove oldest cell                           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### Матрица использования данных

| Поле | Ph1 | Ph2a | Ph2b | Ph3 | Ph4 | Примечание |
|------|-----|------|------|-----|-----|------------|
| **CHARACTER** |
| identity.id | — | ✓ | — | ✓ | — | key в intentions, master |
| identity.name | ✓ | ✓ | ✓ | — | ✓ | везде где персонаж |
| identity.description | ✓ | ✓ | ✓ | — | ✓ | характер |
| identity.triggers | ✓ | ✓ | ✓ | — | — | реакции |
| state.location | ✓* | ✓* | ✓ | **W** | — | *выбор персонажей |
| state.internal_state | ✓ | ✓ | ✓→✓ | **W** | — | before→after в 2b |
| state.external_intent | ✓ | ✓ | ✓→✓ | **W** | — | before→after в 2b |
| memory.cells[].text | ✓ | — | — | **W** | ✓ | oldest в ph4 |
| memory.cells[].tick | — | — | — | **W** | — | техническое |
| memory.summary | ✓ | — | — | **W** | ✓ | сжатая история |
| **LOCATION** |
| identity.id | — | ✓ | — | ✓ | — | ключ локации |
| identity.name | ✓ | ✓ | ✓ | — | — | |
| identity.description | ✓ | ✓ | ✓ | **W** | — | редко меняется |
| identity.connections | ✓ | ✓ | ✓ | — | — | куда идти |
| state.moment | ✓ | ✓ | ✓→✓ | **W** | — | before→after в 2b |
| **OTHER** |
| intentions{} | — | ✓ | ✓ | — | — | Phase 1 output |
| master_result | — | — | ✓ | ✓ | — | Phase 2a output |
| narrative | — | — | — | — | — | Phase 2b output (лог) |
| simulation.current_tick | — | ✓ | — | — | ✓ | в user prompt |

**Легенда:** ✓ = читается, **W** = записывается, ✓→✓ = before→after, * = неявно (для сборки)
