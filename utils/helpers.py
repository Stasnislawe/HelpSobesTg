import asyncio
import logging
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest


logger = logging.getLogger(__name__)


async def safe_send(
    message: Message,
    text: str,
    parse_mode: str = None,
    reply_markup=None,
    max_retries: int = 2,
    delay: float = 1.0
):
    """
    Отправляет сообщение, разбивая на части если превышает лимит 4096 символов.
    При ошибке парсинга Markdown автоматически отправляет без форматирования.
    Возвращает первое отправленное сообщение (или None, если ничего не отправлено).
    """
    parts = split_text(text, max_length=4000)
    first_msg = None
    first = True
    for part in parts:
        if first:
            first_msg = await _send_part(message, part, parse_mode, reply_markup, max_retries, delay)
            first = False
        else:
            await _send_part(message, part, parse_mode, None, max_retries, delay)
    return first_msg


async def _send_part(
    message: Message,
    text: str,
    parse_mode: str,
    reply_markup,
    max_retries: int,
    delay: float
):
    for attempt in range(max_retries):
        try:
            return await message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
        except TelegramBadRequest as e:
            if "can't parse entities" in str(e) and parse_mode:
                logger.warning(f"Markdown parse error, sending without formatting: {e}")
                return await message.answer(text, parse_mode=None, reply_markup=reply_markup)
            elif attempt < max_retries - 1:
                logger.warning(f"Send failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to send message after {max_retries} attempts: {e}")
                raise
    return None


def split_text(text: str, max_length: int = 4000) -> list:
    if len(text) <= max_length:
        return [text]
    parts = []
    remaining = text
    while remaining:
        if len(remaining) <= max_length:
            parts.append(remaining)
            break
        split_pos = remaining.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = remaining.rfind(' ', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        parts.append(remaining[:split_pos])
        remaining = remaining[split_pos:].lstrip()
    return parts


def escape_markdown(text: str) -> str:
    special_chars = r'_*[]()~>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text