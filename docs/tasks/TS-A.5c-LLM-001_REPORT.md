# Task TS-A.5c-LLM-001 Completion Report

## Summary

Implemented LLMClient — provider-agnostic facade for LLM requests. This is the final piece of LLM infrastructure that phases will use for all LLM interactions. The implementation includes:

- `LLMRequest` dataclass for batch execution
- `ResponseChainManager` for managing response chains in entities
- `LLMClient` with single and batch request methods, chain management, and usage accumulation

## Changes Made

### New Files

1. **src/utils/llm.py** — Main module with three classes:
   - `LLMRequest`: Dataclass holding request data (instructions, input_data, schema, entity_key, depth_override)
   - `ResponseChainManager`: Stateless helper for managing response chains in entity dictionaries. Implements sliding window eviction with configurable depth
   - `LLMClient`: Provider-agnostic facade with `create_response()` for single requests and `create_batch()` for parallel execution via `asyncio.gather()`

2. **src/utils/__init__.py** — Updated with exports for `LLMClient`, `LLMRequest`, `ResponseChainManager`

3. **tests/unit/test_llm.py** — 50 comprehensive unit tests covering:
   - ResponseChainManager initialization, get_previous, confirm, parse_key
   - LLMClient initialization, create_response, create_batch
   - Usage accumulation
   - LLMRequest dataclass

4. **tests/integration/test_llm_integration.py** — 8 integration tests with real OpenAI API:
   - Sliding window eviction
   - Chain context preservation
   - Independent requests (depth=0)
   - Batch with chains
   - Usage accumulation
   - Edge cases

## Tests

### Unit Tests
- **Result**: PASS (50/50)
- **Coverage**: 98% for src/utils/llm.py
- Missing lines: 136, 388, 391 (debug logging and edge case branches)

### Integration Tests
- **Result**: PASS (8/8)
- All tests completed in 77 seconds
- Verified real OpenAI API behavior including response deletion

## Quality Checks

| Check | Result |
|-------|--------|
| ruff check | PASS |
| ruff format | PASS |
| mypy | PASS |

## Issues Encountered

1. **mypy type hints**: Required adding `Any` type for dict parameters and `cast()` for chain[-1] return value. Fixed by using `dict[str, Any]` and explicit casts.

2. **Return types for batch methods**: Changed from generic `T | LLMError` to `BaseModel | LLMError` to satisfy mypy, as the actual types are determined at runtime.

## Design Decisions

1. **No rate limit logging in LLMClient**: Per discussion, adapter already logs retries, so removed this requirement from LLMClient.

2. **Thread safety**: Documented that each entity_key should appear at most once in a batch. Not adding locks — this is on caller responsibility.

3. **Usage accumulation skipped for entity_key=None**: Independent requests without entity binding don't accumulate usage anywhere.

## Next Steps

None — LLM infrastructure is complete. Ready for vertical slice development (phases).

## Commit Proposal

```
feat: implement LLMClient facade for provider-agnostic LLM requests
```

## Specs Updated

- `docs/specs/util_llm.md` — No updates needed, implementation matches spec
