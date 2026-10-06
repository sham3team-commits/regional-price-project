from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from catalog.models import Product


class Basket(models.Model):
    name = models.CharField(_("nomi"), max_length=150, unique=True)
    description = models.TextField(_("tavsif"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("savat")
        verbose_name_plural = _("savatlar")

    def __str__(self):
        return self.name


class BasketItem(models.Model):
    basket = models.ForeignKey(Basket, on_delete=models.CASCADE, related_name="items", verbose_name=_("savat"))
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+", verbose_name=_("mahsulot"))
    quantity = models.DecimalField(
        _("miqdor"), max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )

    class Meta:
        ordering = ["pk"]
        verbose_name = _("savat elementi")
        verbose_name_plural = _("savat elementlari")
        constraints = [
            models.UniqueConstraint(fields=["basket", "product"], name="unique_product_per_basket"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="basket_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.product} × {self.quantity}"
