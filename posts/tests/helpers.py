from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

from posts.models import Post, Rubric


def rubric(code="prices"):
    return Rubric.objects.get(code=code)  # created by the 0002_default_rubrics data migration


def make_post(status=Post.Status.SCHEDULED, minutes_from_now=-1, **extra):
    return Post.objects.create(
        rubric=extra.pop("rubric", None) or rubric(),
        text=extra.pop("text", "Narxlar"),
        status=status,
        scheduled_at=timezone.now() + timedelta(minutes=minutes_from_now),
        **extra,
    )


class FakeBot:
    """Stands in for aiogram.Bot: records calls, or raises a prepared exception."""

    def __init__(self, error=None, message_id=777, webhook_url=""):
        self.error = error
        self.message_id = message_id
        self.webhook_url = webhook_url
        self.sent = []
        self.deleted = []

    async def send_message(self, chat_id, text):
        return self._send(chat_id, text)

    async def send_photo(self, chat_id, photo, caption):
        return self._send(chat_id, caption)

    async def get_webhook_info(self):
        return SimpleNamespace(url=self.webhook_url)

    async def delete_message(self, chat_id, message_id):
        if self.error:
            raise self.error
        self.deleted.append((chat_id, message_id))
        return True

    def _send(self, chat_id, text):
        if self.error:
            raise self.error
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=self.message_id)
