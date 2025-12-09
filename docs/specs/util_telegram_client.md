# util_telegram_client.md

## Status: READY

Async HTTP client for Telegram Bot API. Transport layer only — no business logic
for message formatting. Handles retries, rate limiting, and automatic message splitting.

---

## Public API

### split_message

Module-level function for splitting long text into Telegram-compatible parts.

```python
def split_message(text: str, max_length: int = 3896) -> list[str]
```

Splits text into parts that fit Telegram's 4096 character limit.

- **Input**:
  - text — original text to split
  - max_length — maximum length per part (default 3896, includes safety margin)
- **Returns**: List of text parts. If multiple parts, each ends with ` (M/N)` suffix.
- **Behavior**:
  1. If `len(text) <= max_length` → returns `[text]` without suffix
  2. Otherwise splits by paragraphs (`\n\n`)
  3. Accumulates paragraphs until limit reached
  4. If single paragraph > max_length → splits by sentences (`.!?` + space)
  5. If single sentence > max_length → splits by words
  6. Adds ` (M/N)` suffix to each part

### TelegramClient

Async HTTP client for sending messages via Telegram Bot API.

```python
class TelegramClient:
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
    
    async def __aenter__(self) -> TelegramClient
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
```

#### TelegramClient.\_\_init\_\_(...) -> None

Creates client instance with configuration.

- **Input**:
  - bot_token — Telegram bot token from BotFather
  - max_retries — max retry attempts for failed requests (default 3)
  - retry_delay — base delay between retries in seconds (default 1.0)
  - connect_timeout — connection timeout in seconds (default 5.0)
  - read_timeout — read timeout in seconds (default 30.0)
- **Behavior**:
  - Creates `httpx.AsyncClient` with configured timeouts
  - Stores configuration for retry logic
- **Note**: Does not validate bot_token format. Invalid tokens will fail on first request.

#### TelegramClient.send_message(...) -> bool

Sends text message to chat. Automatically splits long messages.

- **Input**:
  - chat_id — numeric chat/channel ID (can be without minus prefix — auto-detected)
  - text — message text (HTML formatted)
  - parse_mode — Telegram parse mode (default "HTML")
- **Returns**: `True` if all message parts sent successfully, `False` on any error
- **Behavior**:
  1. Auto-resolves chat_id format on first use (tries: as-is, `-ID`, `-100ID`)
  2. Caches resolved format for subsequent calls
  3. Splits text using `split_message()` if needed
  4. Sends each part sequentially
  5. On error (429, 5xx, network) — retries with exponential backoff
  6. After `max_retries` failures — logs error, returns `False`
  7. On 4xx (except 429) — logs error, returns `False` immediately (no retry)
- **Note**: Never raises exceptions. All errors are logged and result in `False`.
- **Chat ID formats**: User can provide just the number (e.g., `"5085301047"`), client automatically detects correct format:
  - Personal chats: positive number
  - Groups: negative number (`-5085301047`)
  - Supergroups/Channels: -100 prefix (`-1005085301047`)

#### TelegramClient.close() -> None

Closes underlying HTTP client. Safe to call multiple times.

#### Context Manager

```python
async with TelegramClient(token) as client:
    await client.send_message(chat_id, "Hello")
# client.close() called automatically
```

---

## Internal Design

### HTTP Request

```python
POST https://api.telegram.org/bot{token}/sendMessage
Content-Type: application/json

{
    "chat_id": "123456789",
    "text": "Message text",
    "parse_mode": "HTML"
}
```

### Retry Logic

```python
for attempt in range(max_retries + 1):
    try:
        response = await client.post(url, json=payload)
        
        if response.status_code == 200:
            return True
        
        if response.status_code == 429:
            # Rate limit - get delay from Retry-After header
            retry_after = int(response.headers.get("Retry-After", "1"))
            wait = retry_after + 0.5  # Add buffer
        elif response.status_code >= 500:
            # Server error - exponential backoff
            wait = retry_delay * (2 ** attempt)
        else:
            # Client error (4xx except 429) - no retry
            logger.error("Telegram API error: %d", response.status_code)
            return False
        
        if attempt < max_retries:
            logger.warning("Retry %d/%d after %.1fs", attempt + 1, max_retries, wait)
            await asyncio.sleep(wait)
    
    except Exception as e:
        if attempt >= max_retries:
            logger.error("Failed to send message: %s", e)
            return False
        wait = retry_delay * (2 ** attempt)
        logger.warning("Network error, retry %d/%d after %.1fs", attempt + 1, max_retries, wait)
        await asyncio.sleep(wait)

logger.error("All retry attempts exhausted")
return False
```

### Message Splitting Algorithm

```python
def split_message(text: str, max_length: int = 3896) -> list[str]:
    if len(text) <= max_length:
        return [text]
    
    parts = []
    
    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    current_part = ""
    
    for para in paragraphs:
        if len(para) > max_length:
            # Paragraph too long - split by sentences
            para = _split_by_sentences(para, max_length)
        
        if len(current_part) + len(para) + 2 <= max_length:
            current_part += ("\n\n" if current_part else "") + para
        else:
            if current_part:
                parts.append(current_part)
            current_part = para
    
    if current_part:
        parts.append(current_part)
    
    # Add suffixes
    if len(parts) > 1:
        parts = [f"{p} ({i+1}/{len(parts)})" for i, p in enumerate(parts)]
    
    return parts
```

### Sentence Splitting

Splits by sentence terminators: `.`, `!`, `?` followed by space or end of string.

```python
def _split_by_sentences(text: str, max_length: int) -> str:
    # Implementation splits on '. ', '! ', '? '
    # Falls back to word splitting if sentence > max_length
```

### Word Splitting

Last resort — splits on spaces, keeping words intact where possible.

---

## Configuration Dependency

Bot token is passed directly to constructor. In the application:

```python
# Token from .env via Config
config = Config.load()
client = TelegramClient(config.telegram_bot_token)
```

---

## Logging

Uses standard `logging` module:

```python
logger = logging.getLogger(__name__)
```

| Level | When | Example |
|-------|------|---------|
| DEBUG | Each request sent | `"Sending message to %s (part %d/%d, %d chars)"` |
| WARNING | Retry attempt | `"Rate limit, waiting %.1fs (attempt %d/%d)"` |
| ERROR | All retries exhausted | `"Failed to send to %s after %d attempts: %s"` |

---

## Dependencies

- **Standard Library**: asyncio, logging
- **External**: httpx>=0.27.0
- **Internal**: None

---

## File Structure

```
src/utils/
└── telegram_client.py    # TelegramClient class + split_message function
```

---

## Usage Examples

### Basic Usage

```python
from src.utils.telegram_client import TelegramClient

async def send_notification():
    async with TelegramClient("123456:ABC-token") as client:
        success = await client.send_message(
            chat_id="-1001234567890",
            text="<b>Hello</b> World!",
        )
        if not success:
            print("Failed to send message")
```

### Long Message

```python
async with TelegramClient(token) as client:
    long_text = "..." * 5000  # 15000 chars
    # Automatically splits into multiple messages with (1/N) suffixes
    success = await client.send_message(chat_id, long_text)
```

### Testing split_message

```python
from src.utils.telegram_client import split_message

# Short text - no split
parts = split_message("Hello")
assert parts == ["Hello"]

# Long text - splits with suffixes
parts = split_message("A" * 5000)
assert len(parts) > 1
assert parts[0].endswith("(1/2)")
```

### With Custom Timeouts

```python
client = TelegramClient(
    bot_token=token,
    max_retries=5,
    retry_delay=2.0,
    connect_timeout=10.0,
    read_timeout=60.0,
)
```

---

## Test Coverage

### Unit Tests (tests/unit/test_telegram_client.py)

**split_message function (no mocks):**
- test_split_short_text — text under limit returns single item without suffix
- test_split_by_paragraphs — splits on `\n\n`, adds suffixes
- test_split_long_paragraph — falls back to sentence splitting
- test_split_long_sentence — falls back to word splitting
- test_suffix_format — verifies ` (M/N)` format

**TelegramClient with mocked httpx:**
- test_send_success — 200 response returns True
- test_retry_on_429 — rate limit triggers retry with Retry-After delay
- test_retry_on_5xx — server error triggers exponential backoff
- test_no_retry_on_4xx — client error (except 429) returns False immediately
- test_retries_exhausted — all attempts fail returns False
- test_context_manager — async with calls close()
- test_multi_part_message — long text sends multiple requests

### Integration Tests

File: `tests/integration/test_telegram_client_live.py`

Markers: `@pytest.mark.integration`, `@pytest.mark.telegram`

Skip condition: `TELEGRAM_BOT_TOKEN` or `TELEGRAM_TEST_CHAT_ID` not set in `.env`

Run with: `pytest tests/integration/test_telegram_client_live.py -v -m telegram`

**Configuration**: Tests load credentials from `.env` via `Config.load()` (bot token) and `dotenv` (test chat ID), following the same pattern as other integration tests.

**Tests:**
- test_send_simple_message — sends HTML-formatted message to test chat
- test_send_unicode_message — sends message with Cyrillic and emoji
- test_send_long_message — sends message > 4096 chars (triggers split)
- test_send_to_invalid_chat — verifies graceful failure on invalid chat_id

**Note:** All future Telegram-related integration tests should be added to this file

---

## Error Handling

**Graceful degradation — never raises exceptions:**

| Error Type | Handling |
|------------|----------|
| Network error | Retry with exponential backoff |
| Timeout | Retry with exponential backoff |
| Rate limit (429) | Retry after `Retry-After` seconds |
| Server error (5xx) | Retry with exponential backoff |
| Client error (4xx) | Log error, return False |
| Invalid token | Logged as 401, return False |
| Invalid chat_id | Logged as 400, return False |

All errors logged at appropriate level. Simulation continues even if Telegram fails.

---

## Telegram API Notes

### Limits

- Message length: 4096 characters (including HTML tags)
- Rate limits: 30 msg/sec to channels, 20 msg/sec to groups
- Safe margin: 200 chars reserved for suffix → working limit 3896

### HTML Formatting

Supported tags:
- `<b>bold</b>`
- `<i>italic</i>`
- `<code>monospace</code>`
- `<pre>preformatted</pre>`

Special characters to escape: `<`, `>`, `&`

### chat_id Format

Client automatically detects correct format. User can provide:
- Just the number: `"5085301047"` — client tries all formats
- Already formatted: `"-5085301047"` or `"-1005085301047"` — used as-is

Format detection order:
1. As-is (personal chat)
2. With `-` prefix (regular group)
3. With `-100` prefix (supergroup/channel)

Resolved format is cached per chat_id for performance.

**Note:** `@channel_name` format is NOT supported — use numeric ID only.
