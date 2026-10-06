from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from posts.models import Post

from .helpers import make_post, rubric

Status = Post.Status


class PostEditViewTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("op", is_staff=True))

    def post_data(self, action, **extra):
        return {"rubric": rubric().pk, "language": "uz", "text": "Yangi matn", "action": action, **extra}

    def test_schedule_sets_status(self):
        post = make_post(status=Status.DRAFT)
        response = self.client.post(
            reverse("posts:post_update", args=[post.pk]), self.post_data("schedule", scheduled_at="2030-01-01T09:00")
        )
        self.assertRedirects(response, reverse("posts:post_update", args=[post.pk]))
        post.refresh_from_db()
        self.assertEqual(post.status, Status.SCHEDULED)

    def test_preview_does_not_save(self):
        post = make_post(status=Status.DRAFT, text="Eski")
        response = self.client.post(reverse("posts:post_update", args=[post.pk]), self.post_data("preview"))
        self.assertContains(response, "Yangi matn")
        post.refresh_from_db()
        self.assertEqual(post.text, "Eski")

    def test_post_being_published_cannot_be_edited(self):
        post = make_post(status=Status.PUBLISHING, text="Asl")
        self.client.post(reverse("posts:post_update", args=[post.pk]), self.post_data("draft"))
        post.refresh_from_db()
        self.assertEqual(post.text, "Asl")
        self.assertEqual(post.status, Status.PUBLISHING)

    def test_published_post_comments_can_only_be_turned_off(self):
        post = make_post(status=Status.PUBLISHED, telegram_message_id=5, comments_enabled=True)
        url = reverse("posts:post_update", args=[post.pk])

        self.client.post(url, {})  # checkbox unticked
        post.refresh_from_db()
        self.assertFalse(post.comments_enabled)

        self.client.post(url, {"comments_enabled": "on"})
        post.refresh_from_db()
        self.assertFalse(post.comments_enabled)
