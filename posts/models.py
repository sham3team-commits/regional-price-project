from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from catalog.models import Product
from core.localization import LocalizedNameMixin
from locations.models import City, Store, hashtag_validator

from .hashtags import build_hashtags, split_hashtags


class Rubric(LocalizedNameMixin, models.Model):
    """A content type of the channel. A model (not choices) so the operator can add one in the admin."""

    code = models.SlugField(_("kod"), max_length=50, unique=True)
    name = models.CharField(_("nomi"), max_length=100)
    name_ru = models.CharField(_("nomi (ruscha)"), max_length=100, blank=True)
    hashtag = models.CharField(_("heshteg"), max_length=50, validators=[hashtag_validator])

    class Meta:
        ordering = ["pk"]
        verbose_name = _("rubrika")
        verbose_name_plural = _("rubrikalar")


def hashtags_for(rubric, cities, stores, extra):
    """Hashtags of a post: rubric, cities (direct and via linked stores), extras.

    Shared by Post.hashtags() and PostForm, so the preview and the published
    message can never disagree.
    """
    city_tags = [city.hashtag for city in cities] + [store.city.hashtag for store in stores]
    return build_hashtags(rubric.hashtag if rubric else "", city_tags, split_hashtags(extra))


class PostQuerySet(models.QuerySet):
    def due(self, now):
        return self.filter(status=Post.Status.SCHEDULED, scheduled_at__lte=now).order_by("scheduled_at", "pk")


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        SCHEDULED = "scheduled", _("Rejalashtirilgan")
        # Claimed by the worker; the Telegram request is in flight.
        PUBLISHING = "publishing", _("Yuborilmoqda")
        PUBLISHED = "published", _("Chop etilgan")
        FAILED = "failed", _("Xato")

    rubric = models.ForeignKey(Rubric, on_delete=models.PROTECT, related_name="posts", verbose_name=_("rubrika"))
    language = models.CharField(_("til"), max_length=10, choices=settings.LANGUAGES, default="uz")
    text = models.TextField(_("matn"))
    photo = models.ImageField(_("rasm"), upload_to="posts/", blank=True)
    products = models.ManyToManyField(Product, blank=True, related_name="posts", verbose_name=_("mahsulotlar"))
    stores = models.ManyToManyField(Store, blank=True, related_name="posts", verbose_name=_("do'konlar"))
    cities = models.ManyToManyField(City, blank=True, related_name="posts", verbose_name=_("shaharlar"))
    extra_hashtags = models.CharField(_("qo'shimcha heshteglar"), max_length=255, blank=True)

    comments_enabled = models.BooleanField(_("izohlar yoqilgan"), default=False)
    # Id of the automatic copy of the post in the linked discussion group.
    discussion_message_id = models.BigIntegerField(null=True, blank=True, editable=False)
    # True once the worker deleted that copy, i.e. comments are closed for good.
    comments_closed = models.BooleanField(default=False, editable=False)

    scheduled_at = models.DateTimeField(_("chop etish vaqti"), null=True, blank=True)
    status = models.CharField(_("holat"), max_length=20, choices=Status.choices, default=Status.DRAFT)
    telegram_message_id = models.BigIntegerField(null=True, blank=True, editable=False)
    published_at = models.DateTimeField(null=True, blank=True, editable=False)
    error_message = models.TextField(_("xato matni"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("post")
        verbose_name_plural = _("postlar")
        indexes = [models.Index(fields=["status", "scheduled_at"], name="post_status_scheduled_idx")]
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="scheduled") | Q(scheduled_at__isnull=False),
                name="scheduled_post_has_time",
            ),
            models.CheckConstraint(
                condition=~Q(status="published") | Q(telegram_message_id__isnull=False),
                name="published_post_has_message_id",
            ),
        ]

    def __str__(self):
        first_line = self.text.strip().splitlines()[0] if self.text.strip() else ""
        return f"#{self.pk} {first_line[:60]}"

    def hashtags(self):
        return hashtags_for(self.rubric, self.cities.all(), self.stores.select_related("city"), self.extra_hashtags)

    @property
    def is_locked(self):
        """Publishing or published posts cannot be edited (except closing comments)."""
        return self.status in {self.Status.PUBLISHING, self.Status.PUBLISHED}
