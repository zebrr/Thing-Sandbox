"""Async HTTP client for Telegram Bot API.

Transport layer for sending messages with automatic retry logic,
rate limit handling, and long message splitting. No business logic.

Example:
    >>> from src.utils.telegram_client import TelegramClient
    >>>
    >>> async with TelegramClient("123456:ABC-token") as client:
    ...     success = await client.send_message(
    ...         chat_id="-1001234567890",
    ...         text="<b>Hello</b> World!",
    ...     )
    ...     if not success:
    ...         print("Failed to send")
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# Telegram message limit is 4096 chars, reserve 200 for suffix
DEFAULT_MAX_LENGTH = 3896


def split_message(text: str, max_length: int = DEFAULT_MAX_LENGTH) -> list[str]:
    """Split long text into Telegram-compatible parts.

    Args:
        text: Original text to split.
        max_length: Maximum length per part (default 3896, includes safety margin).

    Returns:
        List of text parts. If multiple parts, each ends with ` (M/N)` suffix.
    """
    if len(text) <= max_length:
        return [text]

    parts: list[str] = []
    paragraphs = text.split("\n\n")
    current_part = ""

    for para in paragraphs:
        # If paragraph itself is too long, split it further
        if len(para) > max_length:
            # Flush current part if any
            if current_part:
                parts.append(current_part)
                current_part = ""
            # Split long paragraph into smaller chunks
            para_parts = _split_long_text(para, max_length)
            parts.extend(para_parts)
            continue

        # Check if paragraph fits in current part
        separator = "\n\n" if current_part else ""
        if len(current_part) + len(separator) + len(para) <= max_length:
            current_part += separator + para
        else:
            # Flush current part and start new one
            if current_part:
                parts.append(current_part)
            current_part = para

    # Don't forget the last part
    if current_part:
        parts.append(current_part)

    # Add suffixes if multiple parts
    if len(parts) > 1:
        total = len(parts)
        parts = [f"{p} ({i + 1}/{total})" for i, p in enumerate(parts)]

    return parts


def _split_long_text(text: str, max_length: int) -> list[str]:
    """Split text that doesn't fit in max_length.

    First tries sentences, then falls back to words.

    Args:
        text: Text to split.
        max_length: Maximum length per part.

    Returns:
        List of text parts (without suffixes).
    """
    # Try splitting by sentences first
    parts = _split_by_sentences(text, max_length)
    if parts:
        return parts

    # Fall back to word splitting
    return _split_by_words(text, max_length)


def _split_by_sentences(text: str, max_length: int) -> list[str]:
    """Split text by sentence terminators.

    Splits on '. ', '! ', '? ' or end of string.

    Args:
        text: Text to split.
        max_length: Maximum length per part.

    Returns:
        List of text parts, or empty list if sentences are too long.
    """
    # Split on sentence terminators followed by space or end
    sentence_pattern = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_pattern.split(text)

    # Check if any sentence is too long
    for sentence in sentences:
        if len(sentence) > max_length:
            return []  # Signal to use word splitting

    parts: list[str] = []
    current_part = ""

    for sentence in sentences:
        separator = " " if current_part else ""
        if len(current_part) + len(separator) + len(sentence) <= max_length:
            current_part += separator + sentence
        else:
            if current_part:
                parts.append(current_part)
            current_part = sentence

    if current_part:
        parts.append(current_part)

    return parts


def _split_by_words(text: str, max_length: int) -> list[str]:
    """Split text by words (spaces).

    Last resort when sentences are too long.

    Args:
        text: Text to split.
        max_length: Maximum length per part.

    Returns:
        List of text parts.
    """
    words = text.split(" ")
    parts: list[str] = []
    current_part = ""

    for word in words:
        # Handle extremely long words (longer than max_length)
        if len(word) > max_length:
            if current_part:
                parts.append(current_part)
                current_part = ""
            # Force split the word
            for i in range(0, len(word), max_length):
                parts.append(word[i : i + max_length])
            continue

        separator = " " if current_part else ""
        if len(current_part) + len(separator) + len(word) <= max_length:
            current_part += separator + word
        else:
            if current_part:
                parts.append(current_part)
            current_part = word

    if current_part:
        parts.append(current_part)

    return parts


def _generate_chat_id_variants(chat_id: str) -> list[str]:
    """Generate possible chat_id formats to try.

    Telegram uses different ID formats:
    - Personal chats: positive number (e.g., "123456789")
    - Groups: negative number (e.g., "-123456789")
    - Supergroups/Channels: -100 prefix (e.g., "-1001234567890")

    Args:
        chat_id: User-provided chat ID (may be any format).

    Returns:
        List of chat_id variants to try, starting with original.
    """
    # Remove any whitespace
    chat_id = chat_id.strip()

    # If already looks correct (has minus or -100), return as-is first
    if chat_id.startswith("-"):
        return [chat_id]

    # User provided positive number - generate variants
    # Try: original, with -, with -100
    variants = [
        chat_id,  # Maybe it's a personal chat
        f"-{chat_id}",  # Regular group
        f"-100{chat_id}",  # Supergroup/channel
    ]
    return variants


class TelegramClient:
    """Async HTTP client for Telegram Bot API.

    Handles message sending with automatic retry logic for rate limits
    and server errors. Never raises exceptions - all errors logged and
    result in False return value.

    Automatically detects correct chat_id format (group vs supergroup).

    Example:
        >>> async with TelegramClient("123456:ABC-token") as client:
        ...     # User can provide just the number, client finds correct format
        ...     await client.send_message("5085301047", "Hello!")
        True
    """

    BASE_URL = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
    ) -> None:
        """Create client instance with configuration.

        Args:
            bot_token: Telegram bot token from BotFather.
            max_retries: Max retry attempts for failed requests (default 3).
            retry_delay: Base delay between retries in seconds (default 1.0).
            connect_timeout: Connection timeout in seconds (default 5.0).
            read_timeout: Read timeout in seconds (default 30.0).
        """
        self._bot_token = bot_token
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._resolved_chat_ids: dict[str, str] = {}  # Cache: user_id -> resolved_id

        timeout = httpx.Timeout(read_timeout, connect=connect_timeout)
        self._client = httpx.AsyncClient(timeout=timeout)

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        message_thread_id: int | None = None,
    ) -> bool:
        """Send text message to chat. Automatically splits long messages.

        Automatically detects correct chat_id format on first use:
        - User can provide just the number (e.g., "5085301047")
        - Client tries variants: as-is, with "-", with "-100"
        - Caches the working format for subsequent calls

        Args:
            chat_id: Numeric chat/channel ID (can be without minus prefix).
            text: Message text (HTML formatted).
            parse_mode: Telegram parse mode (default "HTML").
            message_thread_id: Forum topic ID for supergroups with topics enabled.

        Returns:
            True if all message parts sent successfully, False on any error.
        """
        # Resolve chat_id format if not already cached
        resolved_id = await self._resolve_chat_id(chat_id)
        if resolved_id is None:
            return False

        parts = split_message(text)
        total_parts = len(parts)

        for i, part in enumerate(parts):
            logger.debug(
                "Sending message to %s (part %d/%d, %d chars)",
                resolved_id,
                i + 1,
                total_parts,
                len(part),
            )

            result = await self._send_single_message(
                resolved_id, part, parse_mode, message_thread_id
            )

            # Handle migration: result is new chat_id string
            if isinstance(result, str):
                logger.info(
                    "Updating cached chat_id %s -> %s due to migration",
                    chat_id,
                    result,
                )
                self._resolved_chat_ids[chat_id] = result
                resolved_id = result
                # Retry with new chat_id
                result = await self._send_single_message(
                    resolved_id, part, parse_mode, message_thread_id
                )

            if not result:
                return False

        return True

    async def _resolve_chat_id(self, chat_id: str) -> str | None:
        """Resolve correct chat_id format by trying variants.

        Args:
            chat_id: User-provided chat ID.

        Returns:
            Working chat_id format, or None if all variants failed.
        """
        # Check cache first
        if chat_id in self._resolved_chat_ids:
            return self._resolved_chat_ids[chat_id]

        variants = _generate_chat_id_variants(chat_id)

        # If only one variant (already has minus), use it directly
        if len(variants) == 1:
            self._resolved_chat_ids[chat_id] = variants[0]
            return variants[0]

        # Try each variant with a simple getChat call
        for variant in variants:
            if await self._check_chat_exists(variant):
                logger.debug(
                    "Resolved chat_id %s -> %s",
                    chat_id,
                    variant,
                )
                self._resolved_chat_ids[chat_id] = variant
                return variant

        logger.error(
            "Could not resolve chat_id %s. Tried: %s",
            chat_id,
            ", ".join(variants),
        )
        return None

    async def _check_chat_exists(self, chat_id: str) -> bool:
        """Check if chat exists using getChat API.

        Args:
            chat_id: Chat ID to check.

        Returns:
            True if chat exists and bot has access, False otherwise.
        """
        url = f"{self.BASE_URL}/bot{self._bot_token}/getChat"
        payload = {"chat_id": chat_id}

        try:
            response = await self._client.post(url, json=payload)
            return response.status_code == 200
        except Exception:
            return False

    async def _send_single_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str,
        message_thread_id: int | None = None,
    ) -> bool | str:
        """Send single message with retry logic.

        Args:
            chat_id: Target chat ID.
            text: Message text.
            parse_mode: Telegram parse mode.
            message_thread_id: Forum topic ID for supergroups with topics enabled.

        Returns:
            True on success, False on failure, or new chat_id string if migration detected.
        """
        url = f"{self.BASE_URL}/bot{self._bot_token}/sendMessage"
        payload: dict[str, str | int] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(url, json=payload)

                if response.status_code == 200:
                    return True

                if response.status_code == 429:
                    # Rate limit - get delay from Retry-After header
                    retry_after = int(response.headers.get("Retry-After", "1"))
                    wait = retry_after + 0.5  # Add buffer

                    if attempt < self._max_retries:
                        logger.warning(
                            "Rate limit hit, waiting %.1fs (attempt %d/%d)",
                            wait,
                            attempt + 1,
                            self._max_retries,
                        )
                        await asyncio.sleep(wait)
                        continue

                elif response.status_code >= 500:
                    # Server error - exponential backoff
                    wait = self._retry_delay * (2**attempt)

                    if attempt < self._max_retries:
                        logger.warning(
                            "Server error %d, waiting %.1fs (attempt %d/%d)",
                            response.status_code,
                            wait,
                            attempt + 1,
                            self._max_retries,
                        )
                        await asyncio.sleep(wait)
                        continue

                else:
                    # Client error (4xx except 429) - check for migration
                    if response.status_code == 400:
                        try:
                            data = response.json()
                            migrate_to = data.get("parameters", {}).get("migrate_to_chat_id")
                            if isinstance(migrate_to, int):
                                logger.info(
                                    "Chat %s migrated to %s",
                                    chat_id,
                                    migrate_to,
                                )
                                return str(migrate_to)  # Return new chat_id for retry
                        except Exception:
                            pass  # Failed to parse, fall through to error

                    logger.error(
                        "Telegram API error %d for chat %s: %s",
                        response.status_code,
                        chat_id,
                        response.text[:200],
                    )
                    return False

            except Exception as e:
                if attempt >= self._max_retries:
                    logger.error(
                        "Failed to send to %s after %d attempts: %s",
                        chat_id,
                        attempt + 1,
                        e,
                    )
                    return False

                wait = self._retry_delay * (2**attempt)
                logger.warning(
                    "Network error, waiting %.1fs (attempt %d/%d): %s",
                    wait,
                    attempt + 1,
                    self._max_retries,
                    e,
                )
                await asyncio.sleep(wait)

        # All retries exhausted
        logger.error(
            "Failed to send to %s after %d attempts",
            chat_id,
            self._max_retries + 1,
        )
        return False

    async def close(self) -> None:
        """Close underlying HTTP client. Safe to call multiple times."""
        await self._client.aclose()

    async def __aenter__(self) -> TelegramClient:
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager, closing client."""
        await self.close()
