import asyncio

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter
from aiogram.methods import SendMessage
from asgiref.sync import sync_to_async
from django.test import TestCase, override_settings

from posts import worker
from posts.models import Post

from .helpers import FakeBot, make_post

Status = Post.Status
METHOD = SendMessage(chat_id=1, text="x")


@override_settings(TELEGRAM_CHANNEL_ID="-100123", TELEGRAM_DISCUSSION_GROUP_ID="-100456")
class PublishOneTests(TestCase):
    async def _publish(self, bot):
        post = await sync_to_async(make_post)()
        result = await worker.publish_one(bot, post.pk)
        await post.arefresh_from_db()
        return result, post

    async def test_success_stores_message_id_and_second_call_is_noop(self):
        bot = FakeBot(message_id=4242)
        result, post = await self._publish(bot)

        self.assertTrue(result)
        self.assertEqual(post.status, Status.PUBLISHED)
        self.assertEqual(post.telegram_message_id, 4242)
        self.assertEqual(bot.sent[0][0], "-100123")

        self.assertFalse(await worker.publish_one(bot, post.pk))
        self.assertEqual(len(bot.sent), 1)  # never sent twice

    async def test_bad_request_marks_failed_with_telegram_error(self):
        error = TelegramBadRequest(method=METHOD, message="Bad Request: can't parse entities")
        result, post = await self._publish(FakeBot(error=error))

        self.assertFalse(result)
        self.assertEqual(post.status, Status.FAILED)
        self.assertIn("can't parse entities", post.error_message)

    async def test_network_error_marks_failed_outcome_unknown(self):
        error = TelegramNetworkError(method=METHOD, message="timeout")
        result, post = await self._publish(FakeBot(error=error))

        self.assertEqual(post.status, Status.FAILED)
        self.assertIn("noma'lum", post.error_message)

    async def test_retry_after_puts_post_back_in_schedule(self):
        error = TelegramRetryAfter(method=METHOD, message="Too Many Requests", retry_after=30)
        result, post = await self._publish(FakeBot(error=error))

        self.assertEqual(post.status, Status.SCHEDULED)

    async def test_close_pending_comments_deletes_group_copy(self):
        post = await sync_to_async(make_post)(
            status=Status.PUBLISHED, telegram_message_id=10, discussion_message_id=99, comments_enabled=False
        )
        bot = FakeBot()

        await worker.close_pending_comments(bot)
        await post.arefresh_from_db()

        self.assertEqual(bot.deleted, [("-100456", 99)])
        self.assertTrue(post.comments_closed)

    async def test_already_deleted_group_copy_counts_as_closed(self):
        post = await sync_to_async(make_post)(
            status=Status.PUBLISHED, telegram_message_id=11, discussion_message_id=98, comments_enabled=False
        )
        error = TelegramBadRequest(method=METHOD, message="Bad Request: message to delete not found")

        await worker.close_pending_comments(FakeBot(error=error))
        await post.arefresh_from_db()

        self.assertTrue(post.comments_closed)


class FakeDispatcher:
    def __init__(self, stop):
        self.stop = stop
        self.polled = False

    async def start_polling(self, *args, **kwargs):
        self.polled = True
        self.stop.set()


class PollingLoopTests(TestCase):
    async def test_webhook_blocks_polling_with_a_clear_error(self):
        stop = asyncio.Event()
        bot = FakeBot(webhook_url="https://livegram.io/_run/bot/123:SECRET")
        dispatcher = FakeDispatcher(stop)
        asyncio.get_running_loop().call_later(0.05, stop.set)

        with self.assertLogs("posts.worker", "ERROR") as logs:
            await worker.polling_loop(bot, dispatcher, stop)

        self.assertFalse(dispatcher.polled)
        self.assertIn("livegram.io", logs.output[0])
        self.assertNotIn("SECRET", logs.output[0])  # the token in the URL is never logged

    async def test_polls_when_no_webhook(self):
        stop = asyncio.Event()
        dispatcher = FakeDispatcher(stop)

        await worker.polling_loop(FakeBot(), dispatcher, stop)

        self.assertTrue(dispatcher.polled)
