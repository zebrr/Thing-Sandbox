# Audit Report: Specs vs LLM Documentation

## Summary

Overall consistency is **GOOD**. Specs align well with LLM documentation.
Found 2 minor issues — **both fixed**.

**Documents analyzed:**
- LLM Approach v2 (architecture, chains, retry, batch)
- LLM Prompting (prompt structure, Jinja2, context)
- Phase specs: phase_1.md, phase_3.md
- LLM module specs: util_llm.md, util_llm_adapter_openai.md, util_prompts.md
- JSON Schemas: IntentionResponse.schema.json, Master.schema.json
- Code: phase1.py, phase2a.py, openai.py

---

## Phase Specs vs LLM Approach

### phase_1.md

| Aspect | LLM Approach v2 | phase_1.md | Status |
|--------|-----------------|------------|--------|
| Client interface | LLMClient facade | Uses LLMClient | ✅ OK |
| Batch execution | create_batch() | "All characters processed in parallel via LLMClient.create_batch()" | ✅ OK |
| Entity key format | "intention:{entity_id}" | "intention:{character_id}" | ✅ OK |
| Fallback strategy | Return LLMError in list, phase handles | "idle" fallback + warning + console | ✅ OK |
| Response chains | ChainManager via entity_key | Uses entity_key="intention:{id}" | ✅ OK |
| No OpenAI imports | Phases don't import openai | Imports only LLMClient, LLMRequest, LLMError | ✅ OK |

**Verdict**: Full consistency.

### phase_3.md

| Aspect | LLM Approach v2 | phase_3.md | Status |
|--------|-----------------|------------|--------|
| LLM usage | Phase 3 has no LLM | "Pure mechanics, no LLM" | ✅ OK |
| Data flow | MasterOutput from Phase 2a | Takes master_results dict[str, MasterOutput] | ✅ OK |

**Verdict**: Full consistency.

---

## Phase Specs vs LLM Prompting

### phase_1.md

| Aspect | LLM Prompting | phase_1.md | Status |
|--------|---------------|------------|--------|
| System template | phase1_intention_system.md | References same file | ✅ OK |
| User template | phase1_intention_user.md | References same file | ✅ OK |
| Context variables | character, location, others | Same in "Context Assembly" table | ✅ OK |
| Resolution order | sim override → default | "via PromptRenderer" | ✅ OK |

**Verdict**: Full consistency.

---

## Phase Specs vs JSON Schemas

### IntentionResponse

| Field | Pydantic (phase1.py) | JSON Schema | Status |
|-------|---------------------|-------------|--------|
| intention | `str` (no constraints) | `string`, `minLength: 1` | ⚠️ Mismatch |

**Finding**: JSON Schema requires non-empty string (`minLength: 1`), but Pydantic model allows empty string.

**Impact**: Low. Empty intention would be caught semantically by arbiter. But validation is inconsistent.

### MasterOutput (phase2a.py vs Master.schema.json)

| Field | Pydantic | JSON Schema | Status |
|-------|----------|-------------|--------|
| tick | `int` | `integer`, `minimum: 0` | ✅ OK |
| location_id | `str` | `string` | ✅ OK |
| characters | `dict[str, CharacterUpdate]` | additionalProperties object | ✅ OK |
| location | `LocationUpdate` | object with moment, description | ✅ OK |

**CharacterUpdate fields**: location, internal_state, external_intent, memory_entry — **all match**.

**LocationUpdate fields**: moment (str|None), description (str|None) — **match** JSON Schema's `["string", "null"]`.

**Verdict**: MasterOutput fully consistent.

---

## LLM Module Specs vs LLM Approach

### util_llm.md

| Aspect | LLM Approach v2 | util_llm.md | Status |
|--------|-----------------|-------------|--------|
| LLMClient interface | create_response, create_batch | Same | ✅ OK |
| LLMRequest structure | instructions, input_data, schema, entity_key, depth_override | Same | ✅ OK |
| ResponseChainManager | get_previous, confirm | Same | ✅ OK |
| Auto-confirm | On success, add to chain | Described in Internal Design | ✅ OK |
| Usage accumulation | _openai.usage in entity | Described with code | ✅ OK |
| Chain storage | _openai.{chain}_chain | Same format | ✅ OK |

**Issue found**: Usage Example (line 378-424) shows:
```python
class IntentionResponse(BaseModel):
    intention: str
    target: str | None = None
    reasoning: str
```

But actual IntentionResponse has only `intention: str`. Example is **outdated**.

### util_llm_adapter_openai.md

| Aspect | LLM Approach v2 | util_llm_adapter_openai.md | Status |
|--------|-----------------|---------------------------|--------|
| API method | responses.parse() | Same | ✅ OK |
| text_format param | Pydantic class | Same | ✅ OK |
| Retry policy | Rate limit + timeout | Same | ✅ OK |
| No retry for | Refusal, incomplete | Same | ✅ OK |
| Response processing | Check status, refusal, usage | Same | ✅ OK |
| Delete method | delete_response() | Same | ✅ OK |

**Verdict**: Full consistency with code and LLM Approach.

---

## Prompts Spec vs LLM Prompting

### util_prompts.md

| Aspect | LLM Prompting | util_prompts.md | Status |
|--------|---------------|-----------------|--------|
| Resolution order | sim/prompts/ → src/prompts/ | Same | ✅ OK |
| Jinja2 config | StrictUndefined | Same | ✅ OK |
| Context by phase | Section 3.2 | References LLM Prompting | ✅ OK |
| Template files | 8 files (4 phases × 2) | All exist in src/prompts/ | ✅ OK |

**Verified template files exist:**
- phase1_intention_system.md, phase1_intention_user.md
- phase2a_resolution_system.md, phase2a_resolution_user.md
- phase2b_narrative_system.md, phase2b_narrative_user.md
- phase4_summary_system.md, phase4_summary_user.md

**Verdict**: Full consistency.

---

## ✅ OK

1. **Phase 1 spec** fully aligned with LLM Approach and LLM Prompting
2. **Phase 3 spec** correctly describes no-LLM mechanics
3. **LLM adapter spec** matches code and LLM Approach
4. **Prompts spec** correctly references LLM Prompting
5. **MasterOutput** Pydantic matches JSON Schema
6. **All 8 prompt templates** exist as documented
7. **Response chain management** consistent across all docs

---

## ⚠️ Warnings

### 1. IntentionResponse validation mismatch — ✅ FIXED

**Location**:
- `src/phases/phase1.py:28` — Pydantic model
- `src/schemas/IntentionResponse.schema.json` — JSON Schema

**Issue**: JSON Schema has `minLength: 1`, Pydantic has no constraint.

**Fix applied**: Added `min_length=1` to Pydantic field:
```python
class IntentionResponse(BaseModel):
    intention: str = Field(..., min_length=1)
```

**Test updated**: `tests/unit/test_phase1.py::test_intention_response_empty_string_rejected` — now verifies empty string is rejected.

### 2. Outdated example in util_llm.md — ✅ FIXED

**Location**: `docs/specs/util_llm.md`, lines 370-418 (Usage Examples section)

**Issue**: Example shows IntentionResponse with 3 fields, actual model has 1 field.

**Fix applied**: Updated example to match real IntentionResponse:
```python
class IntentionResponse(BaseModel):
    intention: str = Field(..., min_length=1)
```

Also updated fallback in example to use single-field constructor.

---

## ❌ Issues

None critical.

---

## 📋 Recommendations

### Immediate fixes (from Warnings): ✅ ALL FIXED

1. ~~**Fix IntentionResponse validation** — add `min_length=1` to match JSON Schema~~ ✅ Done
2. ~~**Update util_llm.md example** — use real IntentionResponse structure~~ ✅ Done

### Future consideration:

3. **JSON Schemas as documentation** — CLAUDE.md now clarifies schemas are documentation only. Consider adding comment in JSON files stating "Validation done via Pydantic, this schema is for documentation".
