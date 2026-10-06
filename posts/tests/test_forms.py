from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.factories import make_city
from posts.forms import ACTION_DRAFT, ACTION_SCHEDULE, PostForm
from posts.models import Post

from .helpers import make_post, rubric

# Smallest valid GIF, so ImageField validation passes.
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


class PostFormLengthTests(TestCase):
    def form(self, text, action=ACTION_DRAFT, photo=False, **extra):
        data = {"rubric": rubric().pk, "language": "uz", "text": text, **extra}
        files = {"photo": SimpleUploadedFile("p.gif", TINY_GIF, "image/gif")} if photo else {}
        return PostForm(data, files, action=action)

    def test_text_limit_counts_hashtags(self):
        hashtags_len = len("\n\n#narxlar")
        self.assertTrue(self.form("x" * (4096 - hashtags_len)).is_valid())
        form = self.form("x" * (4096 - hashtags_len + 1))
        self.assertFalse(form.is_valid())
        self.assertIn("text", form.errors)

    def test_caption_limit_with_photo(self):
        self.assertTrue(self.form("x" * 1000, photo=True).is_valid())
        form = self.form("x" * 1020, photo=True)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.preview["limit"], 1024)

    def test_emoji_counts_as_two_units(self):
        hashtags_len = len("\n\n#narxlar")
        self.assertFalse(self.form("🔥" * ((4096 - hashtags_len) // 2 + 1)).is_valid())

    def test_formatting_markers_do_not_count(self):
        hashtags_len = len("\n\n#narxlar")
        self.assertTrue(self.form("**" + "x" * (4096 - hashtags_len) + "**").is_valid())

    def test_schedule_requires_time(self):
        form = self.form("Matn", action=ACTION_SCHEDULE)
        self.assertFalse(form.is_valid())
        self.assertIn("scheduled_at", form.errors)
        self.assertTrue(self.form("Matn", action=ACTION_SCHEDULE, scheduled_at="2030-01-01T09:00").is_valid())

    def test_preview_includes_city_hashtags(self):
        city = make_city("Qo'qon", "qoqon")
        form = self.form("Matn", cities=[city.pk], extra_hashtags="Yangi narx")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["extra_hashtags"], "#yangi #narx")
        self.assertTrue(form.preview["html"].endswith("#narxlar #qoqon #yangi #narx"))

    def test_invalid_extra_hashtag(self):
        form = self.form("Matn", extra_hashtags="#2026")
        self.assertFalse(form.is_valid())
        self.assertIn("extra_hashtags", form.errors)

    def test_closed_comments_cannot_be_reopened(self):
        post = make_post(status=Post.Status.DRAFT, comments_closed=True)
        data = {"rubric": rubric().pk, "language": "uz", "text": "Matn", "comments_enabled": "on"}
        form = PostForm(data, instance=post)
        self.assertFalse(form.is_valid())
        self.assertIn("comments_enabled", form.errors)
