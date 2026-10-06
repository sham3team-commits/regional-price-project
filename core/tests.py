from io import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from baskets.models import Basket
from catalog.models import Product
from locations.models import Store
from posts.models import Post


class PageTests(TestCase):
    """Every operator page renders for staff and redirects anonymous users to the login page."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())
        cls.staff = User.objects.create_user("operator", is_staff=True)

    def urls(self):
        product, store = Product.objects.first(), Store.objects.first()
        basket, post = Basket.objects.first(), Post.objects.first()
        return [
            reverse("dashboard"),
            reverse("catalog:product_list") + "?q=sut",
            reverse("catalog:product_create"),
            reverse("catalog:product_detail", args=[product.pk]),
            reverse("catalog:product_update", args=[product.pk]),
            reverse("catalog:price_entry"),
            reverse("catalog:price_last") + f"?product={product.pk}&store={store.pk}",
            reverse("locations:store_list"),
            reverse("locations:store_create"),
            reverse("locations:store_update", args=[store.pk]),
            reverse("baskets:basket_list"),
            reverse("baskets:basket_create"),
            reverse("baskets:basket_update", args=[basket.pk]),
            reverse("baskets:basket_compare", args=[basket.pk]),
            reverse("posts:post_list") + "?status=draft",
            reverse("posts:post_create"),
            reverse("posts:post_update", args=[post.pk]),
            reverse("posts:generators"),
        ]

    def test_staff_sees_every_page(self):
        self.client.force_login(self.staff)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonymous_is_redirected_to_login(self):
        for url in self.urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("login")))

    def test_non_staff_is_forbidden(self):
        self.client.force_login(User.objects.create_user("customer"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_healthz(self):
        self.assertEqual(self.client.get(reverse("healthz")).json(), {"status": "ok"})

    def test_price_entry_keeps_store_and_saves_new_row(self):
        self.client.force_login(self.staff)
        product, store = Product.objects.first(), Store.objects.first()
        before = product.prices.count()
        response = self.client.post(
            reverse("catalog:price_entry"),
            {"product": product.pk, "store": store.pk, "price": 12300, "recorded_on": "2026-01-05"},
        )
        self.assertRedirects(response, reverse("catalog:price_entry"))
        self.assertEqual(product.prices.count(), before + 1)
        self.assertContains(self.client.get(reverse("catalog:price_entry")), f'<option value="{store.pk}" selected>')


class RussianLanguageTests(TestCase):
    """The RU switch must show the Russian translation and Russian object names."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())
        cls.staff = User.objects.create_user("operator", is_staff=True)

    def setUp(self):
        self.client.force_login(self.staff)

    def test_set_language_switches_interface_to_russian(self):
        self.client.post(reverse("set_language"), {"language": "ru", "next": "/"})
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Главная")
        self.assertContains(response, "Ввод цены")
        self.assertNotContains(response, "Bosh sahifa")

    def test_russian_product_and_city_names(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "ru"
        product = Product.objects.get(name="Shakar")
        response = self.client.get(reverse("catalog:product_detail", args=[product.pk]))
        self.assertContains(response, "<h1>Сахар", html=False)
        self.assertContains(response, "Текущие цены")
        self.assertContains(response, "Коканд")

    def test_uzbek_stays_default(self):
        self.assertContains(self.client.get(reverse("dashboard")), "Bosh sahifa")
