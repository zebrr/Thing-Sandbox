"""Unit tests for Telegram client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.utils.telegram_client import TelegramClient, split_message


class TestSplitMessage:
    """Tests for split_message function."""

    def test_split_short_text(self) -> None:
        """Text under limit returns single item without suffix."""
        text = "Hello, World!"
        result = split_message(text)

        assert result == ["Hello, World!"]
        assert "(1/" not in result[0]

    def test_split_short_text_at_limit(self) -> None:
        """Text exactly at limit returns single item without suffix."""
        text = "A" * 3896
        result = split_message(text, max_length=3896)

        assert len(result) == 1
        assert result[0] == text
        assert "(1/" not in result[0]

    def test_split_by_paragraphs(self) -> None:
        """Splits on paragraph breaks and adds suffixes."""
        para1 = "First paragraph."
        para2 = "Second paragraph."
        text = f"{para1}\n\n{para2}"

        # Use small limit to force split
        result = split_message(text, max_length=25)

        assert len(result) == 2
        assert result[0] == f"{para1} (1/2)"
        assert result[1] == f"{para2} (2/2)"

    def test_split_long_paragraph_to_sentences(self) -> None:
        """Falls back to sentence splitting for long paragraphs."""
        # Create a long paragraph with multiple sentences
        sentences = ["This is sentence one.", "This is sentence two.", "This is sentence three."]
        text = " ".join(sentences)

        # Limit that fits 2 sentences but not 3
        result = split_message(text, max_length=50)

        assert len(result) >= 2
        # Check suffixes present
        assert "(1/" in result[0]
        assert f"/{len(result)})" in result[-1]

    def test_split_long_sentence_to_words(self) -> None:
        """Falls back to word splitting for long sentences."""
        # Create a long sentence without terminators
        text = "word " * 100  # 500 chars
        text = text.strip()

        result = split_message(text, max_length=50)

        assert len(result) > 1
        # Each part should be under limit (minus suffix space)
        for part in result:
            # Parts have suffixes, so actual content is shorter
            assert len(part) <= 60  # Allow some margin for suffix

    def test_suffix_format(self) -> None:
        """Verifies ` (M/N)` format exactly."""
        # Each paragraph is ~10 chars, total ~30+4 = 34 with separators
        # Need max_length that fits one paragraph but not two
        text = "Part one.\n\nPart two.\n\nPart three."

        result = split_message(text, max_length=15)

        assert len(result) == 3
        assert result[0].endswith(" (1/3)")
        assert result[1].endswith(" (2/3)")
        assert result[2].endswith(" (3/3)")

    def test_suffix_has_space_before_parenthesis(self) -> None:
        """Suffix has space before opening parenthesis."""
        # Use longer paragraphs to ensure split happens
        text = "First part here.\n\nSecond part here."
        result = split_message(text, max_length=25)

        assert len(result) == 2
        assert " (1/2)" in result[0]
        assert " (2/2)" in result[1]
        # Verify it's " (" not just "("
        assert result[0][-6] == " "
        assert result[0][-5] == "("

    def test_split_unicode_text(self) -> None:
        """Handles non-ASCII characters correctly."""
        text = "Привет мир! Это тестовое сообщение.\n\nВторой параграф с юникодом."

        result = split_message(text, max_length=50)

        assert len(result) >= 2
        assert "Привет" in result[0]

    def test_extremely_long_word(self) -> None:
        """Handles words longer than max_length."""
        long_word = "A" * 100
        text = f"Hello {long_word} world"

        result = split_message(text, max_length=50)

        # Should split the long word
        assert len(result) > 1


class TestTelegramClient:
    """Tests for TelegramClient class."""

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        """200 response returns True."""
        client = TelegramClient("test-token")
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.send_message("-123456", "Hello")

        assert result is True
        mock_post.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_retry_on_429(self) -> None:
        """Rate limit triggers retry with Retry-After delay."""
        client = TelegramClient("test-token", max_retries=2, retry_delay=0.01)
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        # First response: 429, second response: 200
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}

        success_response = MagicMock()
        success_response.status_code = 200

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [rate_limit_response, success_response]

            with patch(
                "src.utils.telegram_client.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                result = await client.send_message("-123456", "Hello")

        assert result is True
        assert mock_post.call_count == 2
        # Should wait Retry-After + 0.5s buffer
        mock_sleep.assert_called_once_with(1.5)

        await client.close()

    @pytest.mark.asyncio
    async def test_retry_on_5xx(self) -> None:
        """Server error triggers exponential backoff."""
        client = TelegramClient("test-token", max_retries=2, retry_delay=1.0)
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        error_response = MagicMock()
        error_response.status_code = 500

        success_response = MagicMock()
        success_response.status_code = 200

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [error_response, success_response]

            with patch(
                "src.utils.telegram_client.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                result = await client.send_message("-123456", "Hello")

        assert result is True
        assert mock_post.call_count == 2
        # First retry: delay * 2^0 = 1.0
        mock_sleep.assert_called_once_with(1.0)

        await client.close()

    @pytest.mark.asyncio
    async def test_exponential_backoff_5xx(self) -> None:
        """Server errors use exponential backoff."""
        client = TelegramClient("test-token", max_retries=3, retry_delay=1.0)
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        error_response = MagicMock()
        error_response.status_code = 503

        success_response = MagicMock()
        success_response.status_code = 200

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [error_response, error_response, success_response]

            with patch(
                "src.utils.telegram_client.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                result = await client.send_message("-123456", "Hello")

        assert result is True
        assert mock_post.call_count == 3
        # Check exponential backoff: 1.0, 2.0
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)  # 1.0 * 2^0
        mock_sleep.assert_any_call(2.0)  # 1.0 * 2^1

        await client.close()

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self) -> None:
        """Client error (except 429) returns False immediately."""
        client = TelegramClient("test-token", max_retries=3)
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        for status_code in [400, 401, 403, 404]:
            error_response = MagicMock()
            error_response.status_code = status_code
            error_response.text = "Error message"

            with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = error_response
                result = await client.send_message("-123456", "Hello")

            assert result is False
            # Should not retry - only one call
            mock_post.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_retries_exhausted(self) -> None:
        """Returns False after max attempts exhausted."""
        client = TelegramClient("test-token", max_retries=2, retry_delay=0.01)
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        error_response = MagicMock()
        error_response.status_code = 500

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = error_response

            with patch("src.utils.telegram_client.asyncio.sleep", new_callable=AsyncMock):
                result = await client.send_message("-123456", "Hello")

        assert result is False
        # Initial + max_retries attempts
        assert mock_post.call_count == 3

        await client.close()

    @pytest.mark.asyncio
    async def test_network_error_retry(self) -> None:
        """Network errors trigger exponential backoff retry."""
        client = TelegramClient("test-token", max_retries=2, retry_delay=1.0)
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        success_response = MagicMock()
        success_response.status_code = 200

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                httpx.ConnectError("Connection failed"),
                success_response,
            ]

            with patch(
                "src.utils.telegram_client.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                result = await client.send_message("-123456", "Hello")

        assert result is True
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """async with calls close()."""
        with patch.object(httpx.AsyncClient, "aclose", new_callable=AsyncMock) as mock_close:
            async with TelegramClient("test-token") as client:
                assert isinstance(client, TelegramClient)

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_part_message(self) -> None:
        """Long text sends multiple requests."""
        client = TelegramClient("test-token")
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        # Create text that will definitely be split into 2 parts
        # Each part is > 2000 chars, total > 4000 chars
        text = "A" * 2500 + "\n\n" + "B" * 2500

        success_response = MagicMock()
        success_response.status_code = 200

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = success_response
            result = await client.send_message("-123456", text)

        assert result is True
        # Should have sent 2 messages (each paragraph ~2500, limit is 3896)
        assert mock_post.call_count == 2

        await client.close()

    @pytest.mark.asyncio
    async def test_multi_part_fails_on_error(self) -> None:
        """Multi-part message returns False if any part fails."""
        client = TelegramClient("test-token")
        # Pre-populate cache to skip resolution
        client._resolved_chat_ids["-123456"] = "-123456"

        # Create text that will definitely be split into 2 parts
        text = "A" * 2500 + "\n\n" + "B" * 2500

        success_response = MagicMock()
        success_response.status_code = 200

        error_response = MagicMock()
        error_response.status_code = 400
        error_response.text = "Error"

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            # First part succeeds, second fails
            mock_post.side_effect = [success_response, error_response]
            result = await client.send_message("-123456", text)

        assert result is False

        await client.close()

    @pytest.mark.asyncio
    async def test_request_payload(self) -> None:
        """Verifies correct request payload is sent."""
        client = TelegramClient("test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await client.send_message("-1001234567890", "<b>Bold</b>", parse_mode="HTML")

        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check URL
        assert "bot" + "test-token" in call_args[0][0]
        assert "/sendMessage" in call_args[0][0]

        # Check payload
        payload = call_args[1]["json"]
        assert payload["chat_id"] == "-1001234567890"
        assert payload["text"] == "<b>Bold</b>"
        assert payload["parse_mode"] == "HTML"

        await client.close()

    @pytest.mark.asyncio
    async def test_close_safe_multiple_times(self) -> None:
        """Close is safe to call multiple times."""
        client = TelegramClient("test-token")

        # Should not raise
        await client.close()
        await client.close()

    def test_init_stores_config(self) -> None:
        """Init stores configuration correctly."""
        client = TelegramClient(
            bot_token="my-token",
            max_retries=5,
            retry_delay=2.0,
            connect_timeout=10.0,
            read_timeout=60.0,
        )

        assert client._bot_token == "my-token"
        assert client._max_retries == 5
        assert client._retry_delay == 2.0


class TestChatIdResolution:
    """Tests for automatic chat_id format detection."""

    def test_generate_variants_positive_number(self) -> None:
        """Positive number generates all variants."""
        from src.utils.telegram_client import _generate_chat_id_variants

        variants = _generate_chat_id_variants("5085301047")

        assert len(variants) == 3
        assert variants[0] == "5085301047"
        assert variants[1] == "-5085301047"
        assert variants[2] == "-1005085301047"

    def test_generate_variants_negative_number(self) -> None:
        """Negative number returns as-is."""
        from src.utils.telegram_client import _generate_chat_id_variants

        variants = _generate_chat_id_variants("-5085301047")

        assert len(variants) == 1
        assert variants[0] == "-5085301047"

    def test_generate_variants_supergroup_format(self) -> None:
        """Supergroup format (-100) returns as-is."""
        from src.utils.telegram_client import _generate_chat_id_variants

        variants = _generate_chat_id_variants("-1005085301047")

        assert len(variants) == 1
        assert variants[0] == "-1005085301047"

    def test_generate_variants_strips_whitespace(self) -> None:
        """Whitespace is stripped from input."""
        from src.utils.telegram_client import _generate_chat_id_variants

        variants = _generate_chat_id_variants("  5085301047  ")

        assert variants[0] == "5085301047"

    @pytest.mark.asyncio
    async def test_resolve_caches_result(self) -> None:
        """Resolved chat_id is cached for subsequent calls."""
        client = TelegramClient("test-token")

        # Mock _check_chat_exists to return True for group format
        async def mock_check(chat_id: str) -> bool:
            return chat_id == "-5085301047"

        client._check_chat_exists = mock_check  # type: ignore[method-assign]

        # First call - should resolve
        result1 = await client._resolve_chat_id("5085301047")
        assert result1 == "-5085301047"

        # Check it's cached
        assert "5085301047" in client._resolved_chat_ids
        assert client._resolved_chat_ids["5085301047"] == "-5085301047"

        # Second call - should use cache (won't call mock again)
        result2 = await client._resolve_chat_id("5085301047")
        assert result2 == "-5085301047"

        await client.close()

    @pytest.mark.asyncio
    async def test_resolve_returns_none_when_all_fail(self) -> None:
        """Returns None when no variant works."""
        client = TelegramClient("test-token")

        # Mock to always return False
        async def mock_check(chat_id: str) -> bool:
            return False

        client._check_chat_exists = mock_check  # type: ignore[method-assign]

        result = await client._resolve_chat_id("invalid123")
        assert result is None

        await client.close()

    @pytest.mark.asyncio
    async def test_send_with_auto_resolve(self) -> None:
        """send_message auto-resolves chat_id format."""
        client = TelegramClient("test-token")

        # Mock _check_chat_exists to return True for group format
        async def mock_check(chat_id: str) -> bool:
            return chat_id == "-5085301047"

        client._check_chat_exists = mock_check  # type: ignore[method-assign]

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.send_message("5085301047", "Hello")

        assert result is True
        # Verify the resolved ID was used in the actual send
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["chat_id"] == "-5085301047"

        await client.close()
