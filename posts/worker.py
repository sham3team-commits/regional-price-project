"""The publisher worker: an asyncio process with two concurrent tasks.

* scheduler_loop: every PUBLISHER_INTERVAL_SECONDS publishes due posts and
  closes comments that must be off.
* polling_loop: receives messages from the linked discussion group so we learn
  the id of each post's automatic copy there (needed to close its comments).

All database work goes through sync_to_async because the Django ORM is synchronous.
"""

import asyncio
import contextlib
import logging
import signal
from urllib.parse import urlsplit

from aiogram import Dispatcher, F, Router
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramEntityTooLarge,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from aiogram.types import Message, MessageOriginChannel
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections
from django.utils.translation import gettext as _

from . import publisher, telegram

logger = logging.getLogger(__name__)

POLLING_RESTART_DELAY = 10
WEBHOOK_RECHECK_DELAY = 60
LINK_ATTEMPTS = 5


def _outcome_unknown(exc):
    return _("Natija noma'lum (%(error)s). Kanalni tekshiring, kerak bo'lsa qayta rejalashtiring.") % {
        "error": exc.__class__.__name__
    }


async def wait_or_stop(stop, seconds):
    """Sleep up to ``seconds`` but wake up immediately when ``stop`` is set."""
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


async def publish_one(bot, post_id):
    """Publish one due post. Returns True if it was sent.

    The claim happens first: if another process already took the post, we do
    nothing. After the claim every path ends in PUBLISHED, FAILED or (only
    when Telegram certainly rejected the request) SCHEDULED again.
    """
    if not await sync_to_async(publisher.claim)(post_id):
        return False

    try:
        message = await sync_to_async(publisher.build_message)(post_id)
    except Exception as exc:  # nothing was sent, so a definite failure
        logger.exception("Post %s: building the message failed", post_id)
        await sync_to_async(publisher.mark_failed)(post_id, _("Xabarni tayyorlab bo'lmadi: %s") % exc)
        return False

    try:
        message_id = await telegram.send(bot, settings.TELEGRAM_CHANNEL_ID, message)
    except TelegramRetryAfter as exc:
        # 429: Telegram refused the request, so it is safe to try again later.
        logger.warning("Post %s: rate limited, retrying in %ss", post_id, exc.retry_after)
        await sync_to_async(publisher.postpone)(
            post_id, exc.retry_after, _("Telegram cheklovi, %s soniyadan keyin qayta uriniladi.") % exc.retry_after
        )
        return False
    except TelegramEntityTooLarge as exc:
        await sync_to_async(publisher.mark_failed)(post_id, _("Rasm juda katta: %s") % exc.message)
        return False
    except (TelegramNetworkError, TelegramServerError) as exc:
        # The request may have reached Telegram before the connection broke.
        logger.warning("Post %s: outcome unknown: %s", post_id, exc)
        await sync_to_async(publisher.mark_failed)(post_id, _outcome_unknown(exc))
        return False
    except TelegramAPIError as exc:
        # Telegram answered with an error (bad HTML, no rights, wrong chat...): not sent.
        logger.warning("Post %s: rejected by Telegram: %s", post_id, exc.message)
        await sync_to_async(publisher.mark_failed)(post_id, exc.message)
        return False
    except Exception as exc:
        logger.exception("Post %s: unexpected error while sending", post_id)
        await sync_to_async(publisher.mark_failed)(post_id, _outcome_unknown(exc))
        return False

    await sync_to_async(publisher.mark_published)(post_id, message_id)
    logger.info("Post %s published as message %s", post_id, message_id)
    return True


async def close_pending_comments(bot):
    """Delete the discussion-group copy of posts with comments off; this removes their comment thread."""
    for post_id, discussion_message_id in await sync_to_async(publisher.comments_to_close)():
        try:
            await bot.delete_message(settings.TELEGRAM_DISCUSSION_GROUP_ID, discussion_message_id)
        except TelegramBadRequest as exc:
            if "not found" not in exc.message.lower():
                logger.warning("Post %s: could not close comments: %s", post_id, exc.message)
                continue  # try again on the next tick
            # Already deleted (by us in a previous tick or by an admin): closed either way.
        except TelegramAPIError as exc:
            logger.warning("Post %s: could not close comments: %s", post_id, exc)
            continue
        await sync_to_async(publisher.mark_comments_closed)(post_id)
        logger.info("Post %s: comments closed", post_id)


async def tick(bot, stop):
    await sync_to_async(close_old_connections)()
    for post_id in await sync_to_async(publisher.due_post_ids)():
        if stop.is_set():
            return
        await publish_one(bot, post_id)
    await close_pending_comments(bot)


async def scheduler_loop(bot, stop):
    while not stop.is_set():
        try:
            await tick(bot, stop)
        except Exception:
            logger.exception("Scheduler tick failed")
        await wait_or_stop(stop, settings.PUBLISHER_INTERVAL_SECONDS)


def build_dispatcher(bot):
    router = Router()

    @router.message(F.chat.id == int(settings.TELEGRAM_DISCUSSION_GROUP_ID), F.is_automatic_forward)
    async def on_automatic_forward(message: Message):
        """Telegram copies every channel post into the linked group; that copy owns the comment thread."""
        origin = message.forward_origin
        if not isinstance(origin, MessageOriginChannel):
            return
        # The copy can arrive before mark_published has been saved, so retry briefly.
        for _attempt in range(LINK_ATTEMPTS):
            if await sync_to_async(publisher.link_discussion_message)(origin.message_id, message.message_id):
                await close_pending_comments(bot)  # close right away instead of waiting for the next tick
                return
            await asyncio.sleep(1)
        logger.info("Channel message %s is not one of our posts", origin.message_id)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def polling_loop(bot, dispatcher, stop):
    while not stop.is_set():
        try:
            # A bot with a webhook cannot use getUpdates: another service (the
            # webhook owner) receives its updates, so we would never see the
            # discussion-group copies. aiogram would retry that conflict forever
            # without raising, so we check first and say clearly what is wrong.
            webhook = await bot.get_webhook_info()
            if webhook.url:
                logger.error(
                    "The bot has a webhook to %s, so another service receives its updates and comments "
                    "cannot be turned off. Use a dedicated bot, or delete that webhook. Checking again in %ss.",
                    urlsplit(webhook.url).netloc,  # host only: such URLs often contain the token
                    WEBHOOK_RECHECK_DELAY,
                )
                await wait_or_stop(stop, WEBHOOK_RECHECK_DELAY)
                continue
            await dispatcher.start_polling(
                bot, allowed_updates=["message"], handle_signals=False, close_bot_session=False
            )
        except TelegramUnauthorizedError:
            logger.error("Telegram rejected TELEGRAM_BOT_TOKEN; retrying in %ss", POLLING_RESTART_DELAY)
        except Exception:
            logger.exception("Polling crashed, restarting in %ss", POLLING_RESTART_DELAY)
        await wait_or_stop(stop, POLLING_RESTART_DELAY)


async def main():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    recovered = await sync_to_async(publisher.recover_interrupted)()
    if recovered:
        logger.warning("%s post(s) were interrupted while sending and are now marked failed", recovered)

    bot = telegram.make_bot()
    tasks = [asyncio.create_task(scheduler_loop(bot, stop))]
    dispatcher = None
    if settings.TELEGRAM_DISCUSSION_GROUP_ID:
        dispatcher = build_dispatcher(bot)
        tasks.append(asyncio.create_task(polling_loop(bot, dispatcher, stop)))
    else:
        logger.warning("TELEGRAM_DISCUSSION_GROUP_ID is not set: comments cannot be turned off")
    logger.info("Publisher started (interval %ss)", settings.PUBLISHER_INTERVAL_SECONDS)

    await stop.wait()
    logger.info("Stopping publisher...")
    if dispatcher is not None:
        # RuntimeError means polling was not running (e.g. waiting to restart).
        with contextlib.suppress(RuntimeError):
            await dispatcher.stop_polling()
    await asyncio.gather(*tasks, return_exceptions=True)
    await bot.session.close()
    logger.info("Publisher stopped")
