"""Database side of publishing (synchronous ORM code, called from the async worker).

Guarantee: a post is sent to the channel AT MOST ONCE.

1. ``claim`` moves a post from SCHEDULED to PUBLISHING with one conditional
   UPDATE. SQLite executes it atomically, so if two workers (or a worker and
   an operator edit) race, only one sees "1 row updated". Only the winner sends.
2. After Telegram answers, the post becomes PUBLISHED (or FAILED).
3. If the worker dies between 1 and 2 we cannot know whether Telegram got the
   message. ``recover_interrupted`` marks such posts FAILED and asks the
   operator to check the channel instead of retrying: a missing post can be
   rescheduled by hand, a duplicate cannot be taken back.
"""

from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext as _

from .formatting import OutgoingMessage, compose_message, length_limit, message_length, to_telegram_html
from .models import Post

Status = Post.Status


def due_post_ids(now=None):
    return list(Post.objects.due(now or timezone.now()).values_list("pk", flat=True))


def claim(post_id, now=None):
    """Atomically take ownership of a due post. Returns True only for the single winner."""
    now = now or timezone.now()
    updated = Post.objects.filter(pk=post_id, status=Status.SCHEDULED, scheduled_at__lte=now).update(
        status=Status.PUBLISHING, error_message="", updated_at=now
    )
    return updated == 1


def build_message(post_id):
    post = Post.objects.select_related("rubric").get(pk=post_id)
    hashtags = post.hashtags()
    limit = length_limit(bool(post.photo))
    length = message_length(post.text, hashtags)
    if length > limit:
        raise ValueError(_("Matn juda uzun: %(length)s / %(limit)s belgi.") % {"length": length, "limit": limit})
    return OutgoingMessage(
        html=to_telegram_html(compose_message(post.text, hashtags)),
        photo_path=post.photo.path if post.photo else None,
    )


def mark_published(post_id, message_id):
    Post.objects.filter(pk=post_id, status=Status.PUBLISHING).update(
        status=Status.PUBLISHED,
        telegram_message_id=message_id,
        published_at=timezone.now(),
        error_message="",
        updated_at=timezone.now(),
    )


def mark_failed(post_id, error):
    Post.objects.filter(pk=post_id, status=Status.PUBLISHING).update(
        status=Status.FAILED, error_message=error, updated_at=timezone.now()
    )


def postpone(post_id, seconds, reason):
    """Telegram rejected the request (rate limit) so it was NOT sent: safe to schedule again."""
    now = timezone.now()
    Post.objects.filter(pk=post_id, status=Status.PUBLISHING).update(
        status=Status.SCHEDULED, scheduled_at=now + timedelta(seconds=seconds), error_message=reason, updated_at=now
    )


def recover_interrupted():
    """Run at worker start: posts left in PUBLISHING have an unknown outcome. Never auto-retry them."""
    return Post.objects.filter(status=Status.PUBLISHING).update(
        status=Status.FAILED,
        error_message=_(
            "Yuborish paytida worker to'xtadi, natija noma'lum. "
            "Kanalni tekshiring va kerak bo'lsa qayta rejalashtiring."
        ),
        updated_at=timezone.now(),
    )


def link_discussion_message(channel_message_id, discussion_message_id):
    """Remember the id of the post's automatic copy in the discussion group."""
    updated = Post.objects.filter(telegram_message_id=channel_message_id, status=Status.PUBLISHED).update(
        discussion_message_id=discussion_message_id
    )
    return updated == 1


def comments_to_close():
    """(post id, discussion message id) of published posts whose comments must be turned off."""
    return list(
        Post.objects.filter(
            status=Status.PUBLISHED,
            comments_enabled=False,
            comments_closed=False,
            discussion_message_id__isnull=False,
        ).values_list("pk", "discussion_message_id")
    )


def mark_comments_closed(post_id):
    Post.objects.filter(pk=post_id).update(comments_closed=True)
