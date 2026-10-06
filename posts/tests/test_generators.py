from django.test import TestCase

from baskets.models import Basket
from core.factories import add_price, make_city, make_product, make_store
from posts import generators
from posts.models import Post


class GeneratorTests(TestCase):
    def setUp(self):
        self.city = make_city("Qo'qon", "qoqon")
        self.product = make_product("Shakar")

    def test_price_post_lists_cheapest_first_with_hashtags(self):
        add_price(self.product, make_store("Qimmat", self.city), 15000)
        add_price(self.product, make_store("Arzon", self.city), 12500)

        post = generators.price_post(self.product, city=self.city)

        self.assertEqual(post.status, Post.Status.DRAFT)
        self.assertEqual(post.rubric.code, "prices")
        self.assertLess(post.text.index("Arzon"), post.text.index("Qimmat"))
        self.assertIn("12 500", post.text)
        self.assertEqual(post.hashtags(), ["#narxlar", "#qoqon"])
        self.assertNotIn("\n\n\n", post.text)

    def test_no_data_raises_generator_error(self):
        with self.assertRaises(generators.GeneratorError):
            generators.price_post(self.product)
        with self.assertRaises(generators.GeneratorError):
            generators.promotion_post(city=self.city)
        with self.assertRaises(generators.GeneratorError):
            generators.basket_post(Basket.objects.create(name="Bo'sh"))
        with self.assertRaises(generators.GeneratorError):
            generators.new_store_post(make_store(city=self.city, is_new=False))

    def test_new_store_post(self):
        store = make_store("Havas", self.city, is_new=True)
        post = generators.new_store_post(store)
        self.assertIn("Havas", post.text)
        self.assertEqual(post.hashtags(), ["#yangilik", "#qoqon"])

    def test_russian_post_uses_russian_template_and_names(self):
        self.product.name_ru = "Сахар"
        self.product.save()
        add_price(self.product, make_store("Arzon", self.city), 12500)

        post = generators.price_post(self.product, language="ru")

        self.assertEqual(post.language, "ru")
        self.assertIn("Сахар", post.text)
        self.assertIn("Дешевле всего: Arzon — 12 500 сум", post.text)
        self.assertEqual(post.hashtags(), ["#narxlar", "#qoqon"])  # hashtags stay Latin
