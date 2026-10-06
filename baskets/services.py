"""Basket comparison: total cost of a basket in every store, cheapest complete store first."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from catalog.models import Price


@dataclass(frozen=True)
class BasketLine:
    product: object
    quantity: Decimal
    unit_price: int
    on_promo: bool

    @property
    def cost(self):
        return int((self.quantity * self.unit_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class StoreResult:
    store: object
    lines: list = field(default_factory=list)
    missing: list = field(default_factory=list)

    @property
    def total(self):
        # Only products that have a price; missing ones are reported, never counted as 0.
        return sum(line.cost for line in self.lines)

    @property
    def is_complete(self):
        return not self.missing


def compare_basket(basket, city=None, on_date=None):
    """Return a StoreResult per store, ranked: fewest missing products, then cheapest, then name.

    Stores that have no price for any product of the basket are left out.
    """
    on_date = on_date or timezone.localdate()
    items = list(basket.items.select_related("product"))
    if not items:
        return []

    prices = (
        Price.objects.latest_per_store()
        .filter(product__in=[item.product_id for item in items], store__is_active=True)
        .select_related("store__city")
    )
    if city is not None:
        prices = prices.filter(store__city=city)

    by_store = {}
    for entry in prices:
        by_store.setdefault(entry.store, {})[entry.product_id] = entry

    results = []
    for store, entries in by_store.items():
        result = StoreResult(store)
        for item in items:
            entry = entries.get(item.product_id)
            if entry is None:
                result.missing.append(item.product)
            else:
                result.lines.append(
                    BasketLine(item.product, item.quantity, entry.current_value(on_date), entry.promo_active(on_date))
                )
        results.append(result)

    return sorted(results, key=lambda r: (len(r.missing), r.total, r.store.name))
