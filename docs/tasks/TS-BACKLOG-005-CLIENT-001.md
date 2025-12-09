# TS-BACKLOG-005-CLIENT-001: Implement TelegramClient

## References

**Read before starting:**
- Project Architecture for general context
- `docs/specs/util_telegram_client.md` — full specification for this task
- `docs/Thing' Sandbox Telegram API Reference.md` — Telegram Bot API details
- `src/utils/llm_adapters/openai.py` — reference for retry pattern and logging style

## Context

**Current state:** Telegram integration planned, no client implementation exists.

**Goal:** Create async HTTP client for Telegram Bot API as transport layer. The client handles message sending with automatic retry logic and long message splitting. No business logic — just reliable message delivery.

**Key requirements:**
- `split_message()` — public function for splitting long text (testable without mocks)
- `TelegramClient` — async HTTP client with retry logic
- Context manager support (`async with`)
- Graceful degradation — never raises exceptions, returns `False` on failure
- Standard `logging` module for all log output

## Steps

### 1. Create telegram_client.py

Create `src/utils/telegram_client.py` with:

**Public function `split_message(text, max_length=3896) -> list[str]`:**
- If text fits in limit → return `[text]` without suffix
- Otherwise split by paragraphs (`\n\n`)
- If paragraph > limit → split by sentences (`. `, `! `, `? `)
- If sentence > limit → split by words (spaces)
- Add ` (M/N)` suffix to each part when multiple parts

**Class `TelegramClient`:**
```python
def __init__(
    self,
    bot_token: str,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    connect_timeout: float = 5.0,
    read_timeout: float = 30.0,
) -> None

async def send_message(
    self,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
) -> bool

async def close(self) -> None

async def __aenter__(self) -> "TelegramClient"
async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
```

**Retry logic in send_message:**
- 200 → success, return `True`
- 429 → wait `Retry-After` header + 0.5s buffer, retry
- 5xx → exponential backoff (`retry_delay * 2^attempt`), retry
- 4xx (except 429) → log error, return `False` immediately
- Network/timeout error → exponential backoff, retry
- After `max_retries` exhausted → log error, return `False`

**HTTP request format:**
```
POST https://api.telegram.org/bot{token}/sendMessage
Content-Type: application/json
{"chat_id": "...", "text": "...", "parse_mode": "HTML"}
```

**Logging:**
```python
logger = logging.getLogger(__name__)
```
- DEBUG: each request sent (chat_id, text length, part M/N)
- WARNING: retry attempts (attempt number, delay, reason)
- ERROR: all retries exhausted (chat_id, last error)

### 2. Verify requirements.txt

Confirm `httpx>=0.27.0` is present in `requirements.txt` (should already be added).

### 3. Create unit tests

Create `tests/unit/test_telegram_client.py`:

**Tests for split_message (no mocks needed):**
- `test_split_short_text` — under limit returns `[text]` without suffix
- `test_split_by_paragraphs` — splits on `\n\n`, correct suffixes
- `test_split_long_paragraph` — falls back to sentence splitting
- `test_split_long_sentence` — falls back to word splitting
- `test_suffix_format` — verifies ` (M/N)` format exactly

**Tests for TelegramClient (mock httpx):**
- `test_send_success` — 200 response returns `True`
- `test_retry_on_429` — rate limit triggers retry, uses Retry-After
- `test_retry_on_5xx` — server error triggers exponential backoff
- `test_no_retry_on_4xx` — 400/401/403 returns `False` immediately
- `test_retries_exhausted` — returns `False` after max attempts
- `test_context_manager` — `async with` calls `close()`
- `test_multi_part_message` — long text sends multiple requests

**Mocking approach:**
Use `pytest-httpx` or `unittest.mock` to mock `httpx.AsyncClient.post()`.

### 4. Update spec status

Change status in `docs/specs/util_telegram_client.md`:
```markdown
## Status: READY
```

## Testing

**Activate virtual environment first:**
```bash
source venv/bin/activate  # or appropriate command
```

**Quality checks (run BEFORE tests):**
```bash
ruff check src/utils/telegram_client.py tests/unit/test_telegram_client.py
ruff format src/utils/telegram_client.py tests/unit/test_telegram_client.py
mypy src/utils/telegram_client.py
```

**Run tests:**
```bash
pytest tests/unit/test_telegram_client.py -v
```

**Expected result:** All tests pass, no linting errors, no type errors.

**Full test suite (verify no regressions):**
```bash
pytest tests/unit/ -v
```

## Deliverables

- [ ] `src/utils/telegram_client.py` — new module
- [ ] `tests/unit/test_telegram_client.py` — new test file
- [ ] `docs/specs/util_telegram_client.md` — status updated to READY
- [ ] `requirements.txt` — httpx confirmed present
- [ ] All quality checks pass (ruff, mypy)
- [ ] All tests pass
- [ ] Report: `docs/tasks/TS-BACKLOG-005-CLIENT-001_REPORT.md`
