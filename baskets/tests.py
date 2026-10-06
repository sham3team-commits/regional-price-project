from decimal import Decimal

from django.test import TestCase

from core.factories import add_price, make_city, make_product, make_store

from .models import Basket, BasketItem
from .services import compare_basket


class CompareBasketTests(TestCase):
    def setUp(self):
        self.city = make_city("Qo'qon", "qoqon")
        self.sugar = make_product("Shakar")
        self.oil = make_product("Yog'")
        self.basket = Basket.objects.create(name="Weekly")
        BasketItem.objects.create(basket=self.basket, product=self.sugar, quantity=Decimal("2"))
        BasketItem.objects.create(basket=self.basket, product=self.oil, quantity=Decimal("1"))

    def test_ranks_complete_stores_by_total(self):
        cheap = make_store("Cheap", self.city)
        dear = make_store("Dear", self.city)
        add_price(self.sugar, cheap, 10000)
        add_price(self.oil, cheap, 20000)
        add_price(self.sugar, dear, 12000)
        add_price(self.oil, dear, 21000)

        results = compare_basket(self.basket)

        self.assertEqual([r.store for r in results], [cheap, dear])
        self.assertEqual(results[0].total, 40000)
        self.assertEqual(results[1].total, 45000)
        self.assertTrue(results[0].is_complete)

    def test_missing_product_is_reported_not_counted_as_zero(self):
        complete = make_store("Complete", self.city)
        partial = make_store("Partial", self.city)
        add_price(self.sugar, complete, 15000)
        add_price(self.oil, complete, 30000)
        add_price(self.sugar, partial, 1000)  # very cheap, but oil is missing

        results = compare_basket(self.basket)

        self.assertEqual(results[0].store, complete)  # complete stores come first
        self.assertEqual(results[1].store, partial)
        self.assertEqual(results[1].missing, [self.oil])
        self.assertEqual(results[1].total, 2000)  # only the priced line
        self.assertFalse(results[1].is_complete)

    def test_uses_only_latest_price(self):
        store = make_store(city=self.city)
        add_price(self.sugar, store, 99000, days_ago=7)
        add_price(self.sugar, store, 10000, days_ago=0)
        add_price(self.oil, store, 20000)

        self.assertEqual(compare_basket(self.basket)[0].total, 40000)

    def test_city_filter(self):
        other_city = make_city("Andijon", "andijon")
        here = make_store(city=self.city)
        there = make_store(city=other_city)
        for store in (here, there):
            add_price(self.sugar, store, 10000)
            add_price(self.oil, store, 20000)

        results = compare_basket(self.basket, city=other_city)

        self.assertEqual([r.store for r in results], [there])

    def test_fractional_quantity_rounds_half_up(self):
        self.basket.items.all().delete()
        BasketItem.objects.create(basket=self.basket, product=self.sugar, quantity=Decimal("0.5"))
        store = make_store(city=self.city)
        add_price(self.sugar, store, 12345)  # 0.5 × 12345 = 6172.5

        self.assertEqual(compare_basket(self.basket)[0].total, 6173)

    def test_stores_without_any_basket_price_are_excluded(self):
        store = make_store(city=self.city)
        make_store("Empty", self.city)
        add_price(self.sugar, store, 10000)

        self.assertEqual([r.store for r in compare_basket(self.basket)], [store])

    def test_closed_store_is_excluded(self):
        closed = make_store(city=self.city, is_active=False)
        add_price(self.sugar, closed, 10000)

        self.assertEqual(compare_basket(self.basket), [])

    def test_empty_basket(self):
        self.assertEqual(compare_basket(Basket.objects.create(name="Empty")), [])
