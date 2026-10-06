from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.localization import LocalizedNameMixin
from locations.models import Store


class Category(LocalizedNameMixin, models.Model):
    name = models.CharField(_("nomi"), max_length=100, unique=True)
    name_ru = models.CharField(_("nomi (ruscha)"), max_length=100, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("kategoriya")
        verbose_name_plural = _("kategoriyalar")


class Product(LocalizedNameMixin, models.Model):
    class Unit(models.TextChoices):
        KG = "kg", _("kg")
        LITRE = "l", _("litr")
        PIECE = "pcs", _("dona")
        PACK = "pack", _("qadoq")

    name = models.CharField(_("nomi"), max_length=200)
    name_ru = models.CharField(_("nomi (ruscha)"), max_length=200, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", verbose_name=_("kategoriya")
    )
    unit = models.CharField(_("o'lchov birligi"), max_length=10, choices=Unit.choices, default=Unit.PIECE)
    brand = models.CharField(_("brend"), max_length=100, blank=True)
    description = models.TextField(_("tavsif"), blank=True)
    photo = models.ImageField(_("rasm"), upload_to="products/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("mahsulot")
        verbose_name_plural = _("mahsulotlar")
        constraints = [
            models.UniqueConstraint(fields=["name", "brand", "unit"], name="unique_product_name_brand_unit"),
        ]

    def __str__(self):
        label = f"{self.local_name} {self.brand}" if self.brand else self.local_name
        return f"{label} ({self.get_unit_display()})"


class PriceQuerySet(models.QuerySet):
    def latest_per_store(self):
        """Keep only the newest price row for every (product, store) pair.

        SQLite has no DISTINCT ON, so each row is compared with a correlated
        subquery that finds the newest pk for the same product and store.
        Ties on recorded_on are broken by created_at, then pk.
        """
        newest = (
            Price.objects.filter(product=OuterRef("product"), store=OuterRef("store"))
            .order_by("-recorded_on", "-created_at", "-pk")
            .values("pk")[:1]
        )
        return self.filter(pk=Subquery(newest))

    def active_promotions(self, on_date=None):
        """Latest prices that are promotions running on ``on_date``."""
        on_date = on_date or timezone.localdate()
        return (
            self.latest_per_store()
            .filter(is_promo=True, store__is_active=True)
            .filter(Q(promo_starts__isnull=True) | Q(promo_starts__lte=on_date))
            .filter(Q(promo_ends__isnull=True) | Q(promo_ends__gte=on_date))
        )


class Price(models.Model):
    """One observed price of a product in a store on a date.

    The table is append-only: a price change is recorded as a new row, so the
    full history is available for comparisons and charts.
    """

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="prices", verbose_name=_("mahsulot"))
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="prices", verbose_name=_("do'kon"))
    price = models.PositiveIntegerField(_("narx (so'm)"))
    recorded_on = models.DateField(_("sana"), default=timezone.localdate)
    is_promo = models.BooleanField(_("aksiya"), default=False)
    old_price = models.PositiveIntegerField(_("eski narx (so'm)"), null=True, blank=True)
    promo_starts = models.DateField(_("aksiya boshlanishi"), null=True, blank=True)
    promo_ends = models.DateField(_("aksiya tugashi"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PriceQuerySet.as_manager()

    class Meta:
        ordering = ["-recorded_on", "-created_at"]
        verbose_name = _("narx")
        verbose_name_plural = _("narxlar")
        indexes = [
            models.Index(fields=["product", "store", "-recorded_on", "-created_at"], name="price_latest_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name="price_positive"),
            models.CheckConstraint(
                condition=Q(old_price__isnull=True) | Q(old_price__gt=models.F("price")),
                name="old_price_greater_than_price",
            ),
            models.CheckConstraint(
                condition=Q(promo_starts__isnull=True)
                | Q(promo_ends__isnull=True)
                | Q(promo_ends__gte=models.F("promo_starts")),
                name="promo_period_valid",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.store.name}: {self.price}"

    def clean(self):
        errors = {}
        if self.price is not None and self.price <= 0:
            errors["price"] = _("Narx noldan katta bo'lishi kerak.")
        if self.is_promo:
            if not self.old_price:
                errors["old_price"] = _("Aksiya uchun eski narxni kiriting.")
            elif self.price and self.old_price <= self.price:
                errors["old_price"] = _("Eski narx aksiya narxidan katta bo'lishi kerak.")
            if self.promo_starts and self.promo_ends and self.promo_ends < self.promo_starts:
                errors["promo_ends"] = _("Aksiya tugash sanasi boshlanishidan oldin bo'lishi mumkin emas.")
        elif self.old_price or self.promo_starts or self.promo_ends:
            errors["is_promo"] = _("Eski narx va aksiya sanalari faqat aksiya belgilanganda to'ldiriladi.")
        if errors:
            raise ValidationError(errors)

    def promo_active(self, on_date=None):
        if not self.is_promo:
            return False
        on_date = on_date or timezone.localdate()
        started = self.promo_starts is None or self.promo_starts <= on_date
        not_ended = self.promo_ends is None or on_date <= self.promo_ends
        return started and not_ended

    def current_value(self, on_date=None):
        """The price a shopper pays on ``on_date``.

        A promotion row that has expired (or not started yet) falls back to the
        regular price stored in old_price.
        """
        if self.is_promo and self.old_price and not self.promo_active(on_date):
            return self.old_price
        return self.price
