# Task TS-BACKLOG-005-NARRATOR-001 Completion Report

## Summary

Implemented `TelegramNarrator` class that sends tick updates to Telegram channel via lifecycle methods (`on_tick_start`, `on_phase_complete`). Added `escape_html` helper function for HTML escaping.

## Changes Made

### src/narrators.py

- Added imports: `Any` from typing, `BatchStats` from utils.llm, `TelegramClient` from utils.telegram_client
- Added `__all__` export list with `Narrator`, `ConsoleNarrator`, `TelegramNarrator`, `escape_html`
- Added `escape_html(text: str) -> str` function for escaping `&`, `<`, `>` characters
- Added `TelegramNarrator` class with:
  - `__init__`: accepts client, chat_id, mode, group_intentions, group_narratives
  - `on_tick_start`: stores simulation reference, resets phase2a accumulator
  - `on_phase_complete`: routes to appropriate handler based on phase_name
  - `output`: no-op (all messages sent in lifecycle methods)
  - `_send_intentions`: formats and sends intentions (phase1)
  - `_send_intentions_grouped`: single message with all intentions
  - `_send_intentions_per_character`: multiple per-character messages
  - `_send_narratives`: formats and sends narratives (phase2b)
  - `_send_narratives_grouped`: single message with all narratives
  - `_send_narratives_per_location`: multiple per-location messages
  - `_format_stats_footer`: generates stats footer for _stats modes

### tests/unit/test_narrators.py

- Added 5 tests for `escape_html`:
  - test_escape_html_ampersand
  - test_escape_html_less_than
  - test_escape_html_greater_than
  - test_escape_html_combined
  - test_escape_html_no_change

- Added mock classes: `MockBatchStats`, `MockIntentionResponse`, `MockNarrativeResponse`, `MockCharacter`, `MockLocation`, `MockIdentity`, `MockTelegramClient`

- Added 17 tests for `TelegramNarrator`:
  - test_telegram_narrator_protocol
  - test_on_tick_start_stores_simulation
  - test_on_tick_start_resets_phase2a_stats
  - test_on_phase_complete_phase1_sends_intentions
  - test_on_phase_complete_phase1_skipped_for_narratives_mode
  - test_on_phase_complete_phase2a_stores_stats
  - test_on_phase_complete_phase2b_sends_narratives
  - test_intentions_grouped_single_message
  - test_intentions_per_character_multiple_messages
  - test_narratives_grouped_single_message
  - test_narratives_per_location_multiple_messages
  - test_stats_footer_only_for_stats_modes
  - test_stats_footer_only_on_last_message
  - test_phase2_stats_combined
  - test_output_is_noop
  - test_error_handling_continues
  - test_missing_simulation_logs_warning

### docs/specs/core_narrators.md

- Added `escape_html` to Public API section
- Added full `TelegramNarrator` documentation to Public API section
- Added TelegramNarrator output formats with HTML examples
- Updated Error Handling section with Telegram-specific errors
- Updated Dependencies section with new internal dependencies
- Added TelegramNarrator usage examples
- Updated Test Coverage section with all new tests

## Tests

- Result: PASS
- Existing tests: 16 existing narrators tests still pass
- New tests added: 22 tests (5 escape_html + 17 TelegramNarrator)
- Full test suite: 517 passed

## Quality Checks

- ruff check: PASS
- ruff format: PASS (1 file reformatted)
- mypy: PASS

## Issues Encountered

- Line length errors (E501) for long f-strings in header formatting — resolved by splitting strings
- Missing type parameters for `dict` in method signatures — resolved by adding `dict[str, Any]`

## Next Steps

CLI integration (Workplan Etap 4) — wire TelegramNarrator into CLI based on config.toml

## Commit Proposal

```
feat: implement TelegramNarrator for lifecycle-based message delivery
```

## Specs Updated

- docs/specs/core_narrators.md
