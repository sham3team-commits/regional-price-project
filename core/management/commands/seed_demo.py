"""Fill the database with realistic demo data for the Fergana Valley.

Deterministic (fixed random seed), so the demo looks the same on every machine.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from baskets.models import Basket, BasketItem
from catalog.models import Category, Price, Product
from locations.models import City, Store
from posts.models import Post, Rubric

SEED = 2026
WEEKS = 8
MISSING_SHARE = 0.10

CITIES = [
    ("Qo'qon", "Коканд", "qoqon"),
    ("Farg'ona", "Фергана", "fargona"),
    ("Andijon", "Андижан", "andijon"),
    ("Namangan", "Наманган", "namangan"),
    ("Marg'ilon", "Маргилан", "margilon"),
]

# name, city hashtag, address, price factor, is_new, is_bazaar
STORES = [
    ("Korzinka", "qoqon", "Turkiston ko'chasi, 12", 1.05, False, False),
    ("Makro", "qoqon", "Istiqlol ko'chasi, 45", 1.00, False, False),
    ("Qo'qon dehqon bozori", "qoqon", "Navoiy ko'chasi, 1", 0.92, False, True),
    ("Korzinka", "fargona", "Al-Farg'oniy ko'chasi, 5", 1.06, False, False),
    ("Havas", "fargona", "Mustaqillik ko'chasi, 88", 0.97, True, False),
    ("Farg'ona markaziy bozori", "fargona", "Marg'ilon ko'chasi, 2", 0.93, False, True),
    ("Baraka Market", "andijon", "Bobur shoh ko'chasi, 21", 0.98, False, False),
    ("Makro", "andijon", "Navoiy shoh ko'chasi, 7", 1.01, False, False),
    ("Baraka Market", "namangan", "Uychi ko'chasi, 33", 0.99, True, False),
    ("Havas", "margilon", "Burhoniddin Marg'inoniy ko'chasi, 14", 0.97, False, False),
]

CATEGORIES = [
    ("Bakaleya", "Бакалея"),
    ("Sut mahsulotlari", "Молочные продукты"),
    ("Go'sht va parranda", "Мясо и птица"),
    ("Meva va sabzavotlar", "Фрукты и овощи"),
    ("Ichimliklar", "Напитки"),
    ("Maishiy kimyo", "Бытовая химия"),
]

# name, name_ru, category index, unit, brand, base price (so'm, 2026)
PRODUCTS = [
    ("Shakar", "Сахар", 0, "kg", "", 13500),
    ("Guruch (lazer)", "Рис лазер", 0, "kg", "", 22000),
    ("Guruch (devzira)", "Рис девзира", 0, "kg", "", 34000),
    ("Un (oliy nav)", "Мука высший сорт", 0, "kg", "", 6800),
    ("Paxta yog'i", "Хлопковое масло", 0, "l", "", 24000),
    ("Kungaboqar yog'i", "Подсолнечное масло", 0, "l", "Sof", 27000),
    ("Makaron", "Макароны", 0, "pack", "Makfa", 9500),
    ("Grechka", "Гречка", 0, "kg", "", 18000),
    ("Tuz", "Соль", 0, "kg", "", 3000),
    ("Ko'k choy", "Зелёный чай", 0, "pack", "", 12000),
    ("Qora choy", "Чёрный чай", 0, "pack", "Ahmad Tea", 32000),
    ("No'xat", "Нут", 0, "kg", "", 20000),
    ("Mosh", "Маш", 0, "kg", "", 19000),
    ("Obi non", "Лепёшка", 0, "pcs", "", 4000),
    ("Sut 2,5%", "Молоко 2,5%", 1, "l", "Lactel", 13000),
    ("Qatiq", "Катык", 1, "l", "", 11000),
    ("Smetana 20%", "Сметана 20%", 1, "pack", "", 15000),
    ("Tvorog", "Творог", 1, "kg", "", 38000),
    ("Sariyog' 72,5% (200 g)", "Сливочное масло 72,5% (200 г)", 1, "pack", "", 25000),
    ("Pishloq (Gollandskiy)", "Сыр голландский", 1, "kg", "", 95000),
    ("Tuxum (10 dona)", "Яйца (10 шт.)", 1, "pack", "", 16000),
    ("Mol go'shti", "Говядина", 2, "kg", "", 105000),
    ("Qo'y go'shti", "Баранина", 2, "kg", "", 115000),
    ("Tovuq (butun)", "Курица целая", 2, "kg", "", 36000),
    ("Tovuq son", "Куриные окорочка", 2, "kg", "", 38000),
    ("Kartoshka", "Картофель", 3, "kg", "", 6000),
    ("Piyoz", "Лук", 3, "kg", "", 4000),
    ("Sabzi", "Морковь", 3, "kg", "", 5000),
    ("Pomidor", "Помидоры", 3, "kg", "", 14000),
    ("Bodring", "Огурцы", 3, "kg", "", 10000),
    ("Olma", "Яблоки", 3, "kg", "", 15000),
    ("Banan", "Бананы", 3, "kg", "", 22000),
    ("Coca-Cola 1,5 l", "Кока-Кола 1,5 л", 4, "pcs", "Coca-Cola", 12000),
    ("Mineral suv 1,5 l", "Минеральная вода 1,5 л", 4, "pcs", "Hydrolife", 4000),
    ("Kir yuvish kukuni 3 kg", "Стиральный порошок 3 кг", 5, "pack", "Ariel", 95000),
    ("Idish yuvish vositasi 500 ml", "Средство для мытья посуды 500 мл", 5, "pcs", "Fairy", 19000),
    ("Hojatxona qog'ozi (4 dona)", "Туалетная бумага (4 шт.)", 5, "pack", "Zewa", 22000),
    ("Sovun", "Мыло", 5, "pcs", "Duru", 6000),
    ("Tish pastasi", "Зубная паста", 5, "pcs", "Colgate", 18000),
    ("Oqartiruvchi 1 l", "Отбеливатель 1 л", 5, "pcs", "Belizna", 9000),
]

# Bazaars sell food, not branded drinks or household chemicals.
BAZAAR_CATEGORIES = {0, 1, 2, 3}

BASKETS = [
    (
        "Haftalik savat",
        "Oila uchun bir haftalik asosiy mahsulotlar.",
        [
            ("Shakar", "1"),
            ("Guruch (lazer)", "2"),
            ("Paxta yog'i", "1"),
            ("Un (oliy nav)", "2"),
            ("Tuxum (10 dona)", "1"),
            ("Sut 2,5%", "2"),
            ("Kartoshka", "3"),
            ("Piyoz", "2"),
            ("Mol go'shti", "1"),
            ("Obi non", "7"),
        ],
    ),
    (
        "Nonushta savati",
        "Ikki kishilik nonushta uchun.",
        [
            ("Tuxum (10 dona)", "1"),
            ("Sut 2,5%", "1"),
            ("Sariyog' 72,5% (200 g)", "1"),
            ("Obi non", "2"),
            ("Qora choy", "1"),
            ("Pishloq (Gollandskiy)", "0.3"),
            ("Shakar", "0.5"),
        ],
    ),
    (
        "Tozalik savati",
        "Uy tozaligi uchun oylik to'plam.",
        [
            ("Kir yuvish kukuni 3 kg", "1"),
            ("Idish yuvish vositasi 500 ml", "1"),
            ("Hojatxona qog'ozi (4 dona)", "2"),
            ("Sovun", "3"),
            ("Oqartiruvchi 1 l", "1"),
        ],
    ),
]

LIFEHACK_TEXT = """🥔 **Kartoshkani qanday saqlash kerak?**

Kartoshkani qorong'i, salqin (4–8 °C) va quruq joyda saqlang.
Yorug'da u yashil rangga kiradi — bu qismini albatta kesib tashlang.

▫️ Piyoz bilan yonma-yon qo'ymang: ikkalasi ham tezroq buziladi.
▫️ Muzlatgichda saqlamang — kraxmal shakarga aylanib, ta'mi o'zgaradi.
▫️ Qopga 1–2 ta olma solib qo'ysangiz, ko'karib ketishi sekinlashadi.

Sizning sirlaringiz bormi? Izohlarda yozing! 👇"""


def round_price(value):
    """Round like shops do: to 100 so'm below 10 000, to 500 so'm above."""
    step = 100 if value < 10000 else 500
    return max(step, int(round(value / step)) * step)


class Command(BaseCommand):
    help = "Create realistic demo data (cities, stores, products, 8 weeks of prices, promotions, baskets)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data first.")

    def handle(self, *args, reset=False, **options):
        if Product.objects.exists() and not reset:
            raise CommandError("Products already exist. Use --reset to delete all data and seed again.")
        rng = random.Random(SEED)
        with transaction.atomic():
            if reset:
                self._reset()
            cities = self._cities()
            stores = self._stores(cities)
            products = self._products()
            price_count = self._prices(rng, stores, products)
            promo_count = self._promotions(rng, stores)
            self._baskets(products)
            self._lifehack_post()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(cities)} cities, {len(stores)} stores, {len(products)} products, "
                f"{price_count} prices, {promo_count} promotions, {len(BASKETS)} baskets."
            )
        )

    def _reset(self):
        Post.objects.all().delete()
        BasketItem.objects.all().delete()
        Basket.objects.all().delete()
        Price.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Store.objects.all().delete()
        City.objects.all().delete()

    def _cities(self):
        return {tag: City.objects.create(name=name, name_ru=name_ru, hashtag=tag) for name, name_ru, tag in CITIES}

    def _stores(self, cities):
        today = timezone.localdate()
        stores = []
        for name, city_tag, address, factor, is_new, is_bazaar in STORES:
            store = Store.objects.create(
                name=name,
                city=cities[city_tag],
                address=address,
                opened_on=today - timedelta(days=5) if is_new else None,
                is_new=is_new,
            )
            stores.append((store, factor, is_bazaar))
        return stores

    def _products(self):
        categories = [Category.objects.create(name=name, name_ru=name_ru) for name, name_ru in CATEGORIES]
        products = {}
        for name, name_ru, category_index, unit, brand, base in PRODUCTS:
            product = Product.objects.create(
                name=name, name_ru=name_ru, category=categories[category_index], unit=unit, brand=brand
            )
            products[name] = (product, base, category_index)
        return products

    def _prices(self, rng, stores, products):
        today = timezone.localdate()
        rows = []
        for store, store_factor, is_bazaar in stores:
            for product, base, category_index in products.values():
                if is_bazaar and category_index not in BAZAAR_CATEGORIES:
                    continue
                if rng.random() < MISSING_SHARE:
                    continue  # this store does not sell the product
                value = base * store_factor * rng.uniform(0.95, 1.05)
                for week in range(WEEKS - 1, -1, -1):
                    if rng.random() < 0.05:
                        value *= rng.choice([0.88, 1.12, 1.15])  # occasional jump
                    else:
                        value *= rng.uniform(0.99, 1.012)  # slow drift (inflation)
                    rows.append(
                        Price(
                            product=product,
                            store=store,
                            price=round_price(value),
                            recorded_on=today - timedelta(weeks=week),
                        )
                    )
        Price.objects.bulk_create(rows)
        return len(rows)

    def _promotions(self, rng, stores):
        today = timezone.localdate()
        promos = []
        for store, _factor, is_bazaar in stores:
            if is_bazaar:
                continue
            latest = list(Price.objects.filter(store=store, recorded_on=today).order_by("product__name"))
            for regular in rng.sample(latest, k=min(3, len(latest))):
                promo_price = round_price(regular.price * rng.uniform(0.72, 0.9))
                if promo_price >= regular.price:
                    continue
                promos.append(
                    Price(
                        product=regular.product,
                        store=store,
                        price=promo_price,
                        recorded_on=today,
                        is_promo=True,
                        old_price=regular.price,
                        promo_starts=today - timedelta(days=rng.randint(0, 3)),
                        promo_ends=today + timedelta(days=rng.randint(4, 12)),
                    )
                )
        # Created after the regular rows of the same day, so they get higher pks
        # and latest_per_store picks the promotion.
        Price.objects.bulk_create(promos)
        return len(promos)

    def _baskets(self, products):
        for name, description, items in BASKETS:
            basket = Basket.objects.create(name=name, description=description)
            BasketItem.objects.bulk_create(
                BasketItem(basket=basket, product=products[product_name][0], quantity=Decimal(quantity))
                for product_name, quantity in items
            )

    def _lifehack_post(self):
        post = Post.objects.create(
            rubric=Rubric.objects.get(code="lifehack"), text=LIFEHACK_TEXT, comments_enabled=True
        )
        post.products.set([Product.objects.get(name="Kartoshka")])
