from django.test import SimpleTestCase

from posts.hashtags import build_hashtags, normalize_hashtag, split_hashtags


class NormalizeHashtagTests(SimpleTestCase):
    def test_normalisation(self):
        cases = {
            "#Qo'qon": "qoqon",
            "Farg‘ona": "fargona",
            "Marg`ilon": "margilon",
            "Oʻzbekiston": "ozbekiston",
            "yangi do'kon": "yangi_dokon",
            "arzon-savat": "arzon_savat",
            "chegirma!!": "chegirma",
            "##narxlar": "narxlar",
            "2026yil": "2026yil",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_hashtag(raw), expected)

    def test_rejects_empty_and_digit_only(self):
        for raw in ["", "#", "'''", "2026", "#!!"]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                normalize_hashtag(raw)

    def test_split_extra_field(self):
        self.assertEqual(split_hashtags("#a, b  #c,,#"), ["#a", "b", "#c"])


class BuildHashtagsTests(SimpleTestCase):
    def test_order_is_rubric_cities_extras(self):
        self.assertEqual(
            build_hashtags("narxlar", ["qoqon", "fargona"], ["#shakar"]),
            ["#narxlar", "#qoqon", "#fargona", "#shakar"],
        )

    def test_duplicates_removed_keeping_first(self):
        self.assertEqual(
            build_hashtags("chegirma", ["qoqon", "qoqon"], ["#Qo'qon", "chegirma", "yangi"]),
            ["#chegirma", "#qoqon", "#yangi"],
        )

    def test_empty_rubric_tag_skipped(self):
        self.assertEqual(build_hashtags("", ["qoqon"], []), ["#qoqon"])
