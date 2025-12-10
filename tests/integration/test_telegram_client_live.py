"""Integration tests for TelegramClient with real Telegram API.

These tests require .env file with:
- TELEGRAM_BOT_TOKEN: Bot token from BotFather
- TELEGRAM_TEST_CHAT_ID: Chat/group ID for test messages

Run with: pytest tests/integration/test_telegram_client_live.py -v -m telegram
"""

import os

import pytest
from dotenv import load_dotenv

from src.config import Config
from src.utils.telegram_client import TelegramClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.telegram,
]


@pytest.fixture
def bot_token() -> str:
    """Get bot token from Config (.env), skip if not set."""
    cfg = Config.load()
    if not cfg.telegram_bot_token:
        pytest.skip("TELEGRAM_BOT_TOKEN not set in .env")
    return cfg.telegram_bot_token


@pytest.fixture
def chat_id() -> str:
    """Get test chat ID from .env, skip if not set."""
    # Load .env to get test-specific variable
    load_dotenv()
    test_chat_id = os.environ.get("TELEGRAM_TEST_CHAT_ID")
    if not test_chat_id:
        pytest.skip("TELEGRAM_TEST_CHAT_ID not set in .env")
    return test_chat_id


@pytest.fixture
def thread_id() -> int | None:
    """Get test thread ID from .env (optional)."""
    load_dotenv()
    thread_id_str = os.environ.get("TELEGRAM_TEST_THREAD_ID")
    if thread_id_str:
        return int(thread_id_str)
    return None


class TestTelegramClientLive:
    """Live integration tests with real Telegram API."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_send_simple_message(
        self, bot_token: str, chat_id: str, thread_id: int | None
    ) -> None:
        """Send a simple text message to test chat."""
        async with TelegramClient(bot_token) as client:
            result = await client.send_message(
                chat_id=chat_id,
                text="<b>Test message</b> from TelegramClient integration test",
                message_thread_id=thread_id,
            )

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_send_unicode_message(
        self, bot_token: str, chat_id: str, thread_id: int | None
    ) -> None:
        """Send message with Unicode characters."""
        async with TelegramClient(bot_token) as client:
            result = await client.send_message(
                chat_id=chat_id,
                text="Тестовое сообщение с юникодом 🎉",
                message_thread_id=thread_id,
            )

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_send_long_message(
        self, bot_token: str, chat_id: str, thread_id: int | None
    ) -> None:
        """Send message that exceeds 4096 char limit (triggers split)."""
        # Create message > 4096 chars
        long_text = "Paragraph one. " * 200 + "\n\n" + "Paragraph two. " * 200

        async with TelegramClient(bot_token) as client:
            result = await client.send_message(
                chat_id=chat_id,
                text=long_text,
                message_thread_id=thread_id,
            )

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_send_to_invalid_chat(self, bot_token: str) -> None:
        """Sending to invalid chat returns False (no exception)."""
        async with TelegramClient(bot_token) as client:
            result = await client.send_message(
                chat_id="invalid_chat_id_12345",
                text="This should fail",
            )

        assert result is False
