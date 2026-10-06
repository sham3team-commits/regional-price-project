"""Small helpers that build model instances for the test suites."""

import itertools
from datetime import timedelta

from django.utils import timezone

from catalog.models import Category, Price, Product
from locations.models import City, Store

_counter = itertools.count(1)


def make_city(name=None, hashtag=None):
    n = next(_counter)
    return City.objects.create(name=name or f"City {n}", hashtag=hashtag or f"city{n}")


def make_store(name=None, city=None, **extra):
    n = next(_counter)
    return Store.objects.create(name=name or f"Store {n}", city=city or make_city(), address=f"Street {n}", **extra)


def make_product(name=None, unit=Product.Unit.KG, **extra):
    n = next(_counter)
    category = Category.objects.get_or_create(name="Test category")[0]
    return Product.objects.create(name=name or f"Product {n}", category=category, unit=unit, **extra)


def add_price(product, store, price, days_ago=0, **extra):
    return Price.objects.create(
        product=product, store=store, price=price, recorded_on=timezone.localdate() - timedelta(days=days_ago), **extra
    )
