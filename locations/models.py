from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.localization import LocalizedNameMixin

hashtag_validator = RegexValidator(
    r"^[a-z0-9_]+$",
    _("Faqat kichik lotin harflari, raqamlar va _ belgisi (# belgisisiz)."),
)


class City(LocalizedNameMixin, models.Model):
    name = models.CharField(_("nomi"), max_length=100, unique=True)
    name_ru = models.CharField(_("nomi (ruscha)"), max_length=100, blank=True)
    # Stored without "#": the hashtag builder adds it, so data stays uniform.
    hashtag = models.CharField(_("heshteg"), max_length=50, unique=True, validators=[hashtag_validator])

    class Meta:
        ordering = ["name"]
        verbose_name = _("shahar")
        verbose_name_plural = _("shaharlar")


class StoreQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Store(models.Model):
    name = models.CharField(_("nomi"), max_length=150)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="stores", verbose_name=_("shahar"))
    address = models.CharField(_("manzil"), max_length=255)
    map_url = models.URLField(_("xarita havolasi"), blank=True)
    latitude = models.DecimalField(_("kenglik"), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_("uzunlik"), max_digits=9, decimal_places=6, null=True, blank=True)
    opened_on = models.DateField(_("ochilgan sana"), null=True, blank=True)
    is_new = models.BooleanField(_("yangi do'kon"), default=False)
    # False means the store is closed; its price history is kept.
    is_active = models.BooleanField(_("faol"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["city__name", "name"]
        verbose_name = _("do'kon")
        verbose_name_plural = _("do'konlar")
        constraints = [
            models.UniqueConstraint(fields=["city", "name", "address"], name="unique_store_per_city_address"),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"
