from django.test import SimpleTestCase

from posts.formatting import compose_message, message_length, telegram_length, to_telegram_html, visible_text


class FormattingTests(SimpleTestCase):
    def test_user_text_is_escaped(self):
        self.assertEqual(to_telegram_html("M&M's <3 > 2"), "M&amp;M's &lt;3 &gt; 2")

    def test_markers_become_tags_after_escaping(self):
        self.assertEqual(
            to_telegram_html("**<Arzon>** narx: ~~10 000~~ 8 000"),
            "<b>&lt;Arzon&gt;</b> narx: <s>10 000</s> 8 000",
        )

    def test_html_typed_by_operator_is_not_executed(self):
        self.assertEqual(to_telegram_html("<b>x</b>"), "&lt;b&gt;x&lt;/b&gt;")

    def test_unpaired_markers_stay_literal(self):
        self.assertEqual(to_telegram_html("2 ** 3 and ~~ alone"), "2 ** 3 and ~~ alone")

    def test_visible_text_strips_markers(self):
        self.assertEqual(visible_text("**Shakar** ~~13 000~~ 12 000"), "Shakar 13 000 12 000")

    def test_utf16_length_counts_emoji_as_two(self):
        self.assertEqual(telegram_length("abc"), 3)
        self.assertEqual(telegram_length("🔥"), 2)
        self.assertEqual(telegram_length("o'"), 2)

    def test_compose_and_length_include_hashtags(self):
        self.assertEqual(compose_message("  Matn \n", ["#a", "#b"]), "Matn\n\n#a #b")
        self.assertEqual(message_length("**Hi**", ["#a"]), len("Hi\n\n#a"))
