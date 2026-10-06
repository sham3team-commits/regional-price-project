from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from core.factories import add_price, make_product, make_store

from .models import Price
from .services import current_prices, price_change_alerts, price_history_chart


class PriceModelTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.store = make_store()

    def test_latest_per_store_keeps_newest_row_per_pair(self):
        other = make_store()
        add_price(self.product, self.store, 100, days_ago=14)
        newest = add_price(self.product, self.store, 300, days_ago=0)
        other_newest = add_price(self.product, other, 200, days_ago=3)

        self.assertEqual(set(Price.objects.latest_per_store()), {newest, other_newest})

    def test_same_day_tie_is_broken_by_insertion_order(self):
        add_price(self.product, self.store, 100)
        second = add_price(self.product, self.store, 90)

        self.assertEqual(list(Price.objects.latest_per_store()), [second])

    def test_expired_promotion_falls_back_to_old_price(self):
        today = timezone.localdate()
        promo = add_price(
            self.product,
            self.store,
            8000,
            days_ago=10,
            is_promo=True,
            old_price=10000,
            promo_starts=today - timedelta(days=10),
            promo_ends=today - timedelta(days=1),
        )
        self.assertFalse(promo.promo_active(today))
        self.assertEqual(promo.current_value(today), 10000)
        self.assertEqual(promo.current_value(today - timedelta(days=2)), 8000)

    def test_promo_validation(self):
        cases = [
            ({"is_promo": True}, "old_price"),
            ({"is_promo": True, "old_price": 5000}, "old_price"),  # not greater than price
            ({"old_price": 20000}, "is_promo"),  # promo data without the flag
            (
                {
                    "is_promo": True,
                    "old_price": 20000,
                    "promo_starts": timezone.localdate(),
                    "promo_ends": timezone.localdate() - timedelta(days=1),
                },
                "promo_ends",
            ),
        ]
        for fields, error_field in cases:
            with self.subTest(fields=fields):
                price = Price(product=self.product, store=self.store, price=10000, **fields)
                with self.assertRaises(ValidationError) as ctx:
                    price.full_clean()
                self.assertIn(error_field, ctx.exception.message_dict)

    def test_database_rejects_old_price_below_price(self):
        with self.assertRaises(IntegrityError):
            add_price(self.product, self.store, 10000, is_promo=True, old_price=9000)


class PriceServiceTests(TestCase):
    def setUp(self):
        self.product = make_product()

    def test_current_prices_cheapest_first_and_skip_closed_stores(self):
        dear, cheap = make_store("Dear"), make_store("Cheap")
        closed = make_store("Closed", is_active=False)
        add_price(self.product, dear, 15000)
        add_price(self.product, cheap, 12000)
        add_price(self.product, closed, 1000)

        self.assertEqual([row.store for row in current_prices(self.product)], [cheap, dear])

    def test_chart_has_one_dataset_per_store_with_gaps(self):
        a, b = make_store("A"), make_store("B")
        add_price(self.product, a, 100, days_ago=7)
        add_price(self.product, a, 110, days_ago=0)
        add_price(self.product, b, 120, days_ago=0)

        chart = price_history_chart(self.product)

        self.assertEqual(len(chart["labels"]), 2)
        data = {ds["label"]: ds["data"] for ds in chart["datasets"]}
        self.assertEqual(data[str(a)], [100, 110])
        self.assertEqual(data[str(b)], [None, 120])

    def test_price_change_alerts(self):
        jumped, stable = make_store("Jumped"), make_store("Stable")
        add_price(self.product, jumped, 10000, days_ago=8)
        add_price(self.product, jumped, 12000, days_ago=1)
        add_price(self.product, stable, 10000, days_ago=8)
        add_price(self.product, stable, 10500, days_ago=1)

        alerts = price_change_alerts(10)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].store, jumped)
        self.assertEqual(alerts[0].change_percent, 20.0)
