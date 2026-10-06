"""Read-side price logic: current prices, chart data and price-change alerts."""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from .models import Price


@dataclass(frozen=True)
class CurrentPrice:
    entry: Price
    value: int
    on_promo: bool

    @property
    def store(self):
        return self.entry.store


def current_prices(product, city=None, on_date=None):
    """Latest price of ``product`` in every active store, cheapest first."""
    on_date = on_date or timezone.localdate()
    entries = (
        Price.objects.latest_per_store().filter(product=product, store__is_active=True).select_related("store__city")
    )
    if city is not None:
        entries = entries.filter(store__city=city)
    rows = [CurrentPrice(e, e.current_value(on_date), e.promo_active(on_date)) for e in entries]
    return sorted(rows, key=lambda row: (row.value, row.store.name))


def price_history_chart(product):
    """Chart.js line chart data: one dataset per store, ``None`` where a store has no entry that day."""
    entries = (
        Price.objects.filter(product=product).select_related("store__city").order_by("recorded_on", "created_at", "pk")
    )
    dates = []
    by_store = {}
    for entry in entries:
        day = entry.recorded_on.isoformat()
        if day not in dates:
            dates.append(day)
        # Later entries on the same day overwrite earlier ones (query is ordered).
        by_store.setdefault(entry.store, {})[day] = entry.current_value(entry.recorded_on)
    datasets = [
        {"label": str(store), "data": [values.get(day) for day in dates]}
        for store, values in sorted(by_store.items(), key=lambda item: str(item[0]))
    ]
    return {"labels": dates, "datasets": datasets}


@dataclass(frozen=True)
class PriceAlert:
    product: object
    store: object
    old_value: int
    new_value: int

    @property
    def change_percent(self):
        return round((self.new_value - self.old_value) * 100 / self.old_value, 1)


def price_change_alerts(threshold_percent, days=7, today=None):
    """Products whose current price moved by at least ``threshold_percent`` versus ``days`` ago.

    "Then" is the newest price recorded on or before the cutoff date for the
    same product and store; pairs with no such price are skipped.
    """
    today = today or timezone.localdate()
    cutoff = today - timedelta(days=days)

    then = {}
    older = Price.objects.filter(recorded_on__lte=cutoff).order_by("recorded_on", "created_at", "pk")
    for entry in older:
        then[(entry.product_id, entry.store_id)] = entry  # ordered, so the newest wins

    alerts = []
    latest = (
        Price.objects.latest_per_store()
        .filter(store__is_active=True, recorded_on__gt=cutoff)
        .select_related("product", "store__city")
    )
    for entry in latest:
        previous = then.get((entry.product_id, entry.store_id))
        if previous is None:
            continue
        alert = PriceAlert(
            entry.product, entry.store, previous.current_value(previous.recorded_on), entry.current_value(today)
        )
        if abs(alert.change_percent) >= threshold_percent:
            alerts.append(alert)
    return sorted(alerts, key=lambda a: -abs(a.change_percent))
