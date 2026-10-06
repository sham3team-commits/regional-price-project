from django.test import TestCase
from django.utils import timezone

from core.factories import make_city
from posts import publisher
from posts.models import Post

from .helpers import make_post

Status = Post.Status


class DuePostsTests(TestCase):
    def test_only_scheduled_posts_whose_time_has_come(self):
        due = make_post(minutes_from_now=-5)
        due_now = make_post(minutes_from_now=0)
        make_post(minutes_from_now=10)  # future
        for status in (Status.DRAFT, Status.PUBLISHING, Status.FAILED):
            make_post(status=status, minutes_from_now=-5)
        make_post(status=Status.PUBLISHED, minutes_from_now=-5, telegram_message_id=1)

        self.assertEqual(publisher.due_post_ids(timezone.now()), [due.pk, due_now.pk])

    def test_ordered_by_time(self):
        later = make_post(minutes_from_now=-1)
        earlier = make_post(minutes_from_now=-10)
        self.assertEqual(publisher.due_post_ids(), [earlier.pk, later.pk])


class ClaimTests(TestCase):
    def test_claim_succeeds_only_once(self):
        post = make_post()
        self.assertTrue(publisher.claim(post.pk))
        self.assertFalse(publisher.claim(post.pk))
        post.refresh_from_db()
        self.assertEqual(post.status, Status.PUBLISHING)

    def test_cannot_claim_draft_or_future_post(self):
        self.assertFalse(publisher.claim(make_post(status=Status.DRAFT).pk))
        self.assertFalse(publisher.claim(make_post(minutes_from_now=30).pk))

    def test_recover_interrupted_marks_failed_without_retry(self):
        stuck = make_post(status=Status.PUBLISHING)
        scheduled = make_post()

        self.assertEqual(publisher.recover_interrupted(), 1)

        stuck.refresh_from_db()
        self.assertEqual(stuck.status, Status.FAILED)
        self.assertIn("noma'lum", stuck.error_message)
        self.assertEqual(publisher.due_post_ids(), [scheduled.pk])

    def test_postpone_reschedules_into_the_future(self):
        post = make_post()
        publisher.claim(post.pk)
        publisher.postpone(post.pk, 30, "rate limit")
        post.refresh_from_db()
        self.assertEqual(post.status, Status.SCHEDULED)
        self.assertGreater(post.scheduled_at, timezone.now())


class BuildMessageTests(TestCase):
    def test_message_has_escaped_text_and_hashtags(self):
        post = make_post(text="**Shakar** <arzon>", extra_hashtags="#shirin")
        post.cities.add(make_city("Qo'qon", "qoqon"))

        message = publisher.build_message(post.pk)

        self.assertEqual(message.html, "<b>Shakar</b> &lt;arzon&gt;\n\n#narxlar #qoqon #shirin")
        self.assertIsNone(message.photo_path)

    def test_too_long_message_raises(self):
        post = make_post(text="x" * 4096)
        with self.assertRaises(ValueError):
            publisher.build_message(post.pk)


class CommentsTests(TestCase):
    def test_link_then_queue_for_closing(self):
        post = make_post(status=Status.PUBLISHED, telegram_message_id=50, comments_enabled=False)

        self.assertTrue(publisher.link_discussion_message(50, 900))
        self.assertEqual(publisher.comments_to_close(), [(post.pk, 900)])

        publisher.mark_comments_closed(post.pk)
        self.assertEqual(publisher.comments_to_close(), [])

    def test_enabled_comments_are_left_alone(self):
        make_post(status=Status.PUBLISHED, telegram_message_id=51, comments_enabled=True)
        publisher.link_discussion_message(51, 901)
        self.assertEqual(publisher.comments_to_close(), [])

    def test_unknown_channel_message_is_not_linked(self):
        self.assertFalse(publisher.link_discussion_message(12345, 1))
