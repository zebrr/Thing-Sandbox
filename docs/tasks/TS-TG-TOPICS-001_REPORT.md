# Task TS-TG-TOPICS-001 Completion Report

## Summary

Added optional `message_thread_id` support for sending messages to Telegram forum topics (threads). The parameter flows through the entire configuration chain: `.env` → `config.toml` → `simulation.json` → `resolve_output()` → `TelegramNarrator` → `TelegramClient`.

## Changes Made

### Source Code

- **src/config.py**:
  - Added `telegram_test_thread_id: int | None = None` to `EnvSettings`
  - Added `message_thread_id: int | None = None` to `TelegramOutputConfig`
  - Added `telegram_test_thread_id` parameter and attribute to `Config.__init__`
  - Updated `Config.load()` to pass `telegram_test_thread_id`
  - Added fallback logic in `resolve_output()` for `message_thread_id`

- **src/utils/telegram_client.py**:
  - Added `message_thread_id: int | None = None` parameter to `send_message()`
  - Added `message_thread_id` parameter to `_send_single_message()` and included in payload when not None
  - Added automatic handling of chat migration (`migrate_to_chat_id`) — when a group is upgraded to supergroup, client detects migration response and retries with new chat_id

- **src/narrators.py**:
  - Added `message_thread_id: int | None = None` parameter to `TelegramNarrator.__init__`
  - All `_send_*` methods now pass `message_thread_id` to `send_message()`

- **src/cli.py**:
  - Updated `TelegramNarrator` creation to pass `message_thread_id` from output config

### Configuration Files

- **.env**: Added `TELEGRAM_TEST_THREAD_ID=2`, updated `TELEGRAM_TEST_CHAT_ID` to use plain number without -100 prefix (auto-detection handles format)
- **.env.example**: Added `TELEGRAM_TEST_THREAD_ID=`
- **config.toml**: Added commented `# message_thread_id =` option

### Tests

- **tests/unit/test_config.py**: Added 7 new tests in `TestMessageThreadId` class
- **tests/unit/test_telegram_client.py**: Added 2 new tests for `message_thread_id` payload
- **tests/unit/test_narrators.py**:
  - Updated `MockTelegramClient` to track `message_thread_id`
  - Updated `_make_narrator` helper to accept `message_thread_id`
  - Added 3 new tests for thread_id propagation
- **tests/unit/test_cli.py**: Updated existing test to check `message_thread_id=None`
- **tests/integration/test_telegram_client_live.py**:
  - Added `thread_id` fixture to read `TELEGRAM_TEST_THREAD_ID` from .env
  - Updated all send tests to pass `message_thread_id=thread_id`

### Documentation

- **docs/specs/core_config.md**: Updated with `message_thread_id` field and fallback behavior
- **docs/specs/core_narrators.md**: Updated `TelegramNarrator` signature and added tests
- **docs/specs/util_telegram_client.md**: Updated `send_message` signature and payload example

## Tests

- **Result**: PASS (536 unit tests passed + 4 integration tests passed)
- **Existing tests modified**:
  - `test_cli_creates_telegram_narrator` (added `message_thread_id=None` assertion)
  - `MockTelegramClient` in `test_narrators.py` (added `message_thread_id` tracking)
- **New tests added**:
  - `test_message_thread_id_default`
  - `test_message_thread_id_custom`
  - `test_env_loading_with_thread_id`
  - `test_output_config_from_toml_with_thread_id`
  - `test_resolve_output_fallback_thread_id`
  - `test_resolve_output_no_fallback_when_thread_id_set`
  - `test_resolve_output_partial_override_thread_id`
  - `test_send_message_with_thread_id`
  - `test_send_message_without_thread_id`
  - `test_message_thread_id_passed_to_client`
  - `test_message_thread_id_none_passed_to_client`
  - `test_narratives_pass_thread_id`

## Quality Checks

- ruff check: PASS
- ruff format: PASS
- mypy: PASS

## Issues Encountered

- Integration tests initially failed due to Telegram group migration (group → supergroup). Added automatic `migrate_to_chat_id` handling in `TelegramClient` to resolve this.

## Next Steps

None

## Commit Proposal

`feat: add message_thread_id support for Telegram forum topics`

## Specs Updated

- `docs/specs/core_config.md`
- `docs/specs/core_narrators.md`
- `docs/specs/util_telegram_client.md`
