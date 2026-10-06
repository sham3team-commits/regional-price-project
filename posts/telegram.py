"""Thin wrapper around aiogram: the only module that talks to the Telegram Bot API for sending."""

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from django.conf import settings


def make_bot():
    return Bot(
        settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


async def send(bot, chat_id, message):
    """Send an OutgoingMessage as a photo with caption or as text. Returns Telegram's message_id."""
    if message.photo_path:
        sent = await bot.send_photo(chat_id, FSInputFile(message.photo_path), caption=message.html)
    else:
        sent = await bot.send_message(chat_id, message.html)
    return sent.message_id


async def send_once(chat_id, message):
    """One-off send with a short-lived bot (used by the "Send test" button in the web app)."""
    bot = make_bot()
    try:
        return await send(bot, chat_id, message)
    finally:
        await bot.session.close()
