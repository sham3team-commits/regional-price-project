from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from baskets.models import Basket
from catalog.forms import validate_photo_size
from catalog.models import Product
from locations.models import City, Store

from .formatting import compose_message, length_limit, message_length, to_telegram_html
from .hashtags import normalize_hashtag, split_hashtags
from .models import Post, hashtags_for

ACTION_DRAFT = "draft"
ACTION_SCHEDULE = "schedule"
ACTION_PREVIEW = "preview"


class PostForm(forms.ModelForm):
    """Edit form of an unpublished post.

    clean() builds the exact message that will be sent, so the length check
    and the preview use the same text as the worker.
    """

    class Meta:
        model = Post
        fields = [
            "rubric",
            "language",
            "text",
            "photo",
            "products",
            "stores",
            "cities",
            "extra_hashtags",
            "comments_enabled",
            "scheduled_at",
        ]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 14}),
            "products": forms.SelectMultiple(attrs={"data-tom-select": "multi"}),
            "stores": forms.SelectMultiple(attrs={"data-tom-select": "multi"}),
            "cities": forms.SelectMultiple(attrs={"data-tom-select": "multi"}),
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }
        help_texts = {
            "text": _("**qalin** va ~~o'chirilgan~~ formatlash mumkin. Heshteglar avtomatik qo'shiladi."),
            "extra_hashtags": _("Bo'sh joy yoki vergul bilan ajrating, masalan: #shakar #yangi_narx"),
            "scheduled_at": _("Toshkent vaqti bilan."),
        }

    def __init__(self, *args, action=ACTION_DRAFT, **kwargs):
        super().__init__(*args, **kwargs)
        self.action = action
        self.fields["stores"].queryset = Store.objects.select_related("city")
        self.preview = None

    def clean_photo(self):
        return validate_photo_size(self.cleaned_data.get("photo"))

    def clean_extra_hashtags(self):
        tags = split_hashtags(self.cleaned_data["extra_hashtags"])
        try:
            return " ".join("#" + normalize_hashtag(tag) for tag in tags)
        except ValueError:
            raise forms.ValidationError(_("Heshteg harf yoki pastki chiziqni o'z ichiga olishi kerak.")) from None

    def clean(self):
        cleaned = super().clean()
        if self.instance.comments_closed and cleaned.get("comments_enabled"):
            self.add_error("comments_enabled", _("Izohlar yopilgan, ularni qayta yoqib bo'lmaydi."))
        if self.action == ACTION_SCHEDULE and not cleaned.get("scheduled_at"):
            self.add_error("scheduled_at", _("Rejalashtirish uchun vaqtni kiriting."))
        if "text" in cleaned and "rubric" in cleaned:
            hashtags = hashtags_for(
                cleaned["rubric"],
                cleaned.get("cities", []),
                cleaned.get("stores", []),
                cleaned.get("extra_hashtags", ""),
            )
            self.preview = build_preview(cleaned["text"], hashtags, has_photo=bool(cleaned.get("photo")))
            if self.preview["length"] > self.preview["limit"]:
                self.add_error(
                    "text",
                    _("Xabar juda uzun: %(length)s / %(limit)s belgi (heshteglar bilan).") % self.preview,
                )
        return cleaned


def build_preview(text, hashtags, has_photo):
    return {
        "html": to_telegram_html(compose_message(text, hashtags)),
        "length": message_length(text, hashtags),
        "limit": length_limit(has_photo),
        "has_photo": has_photo,
    }


class CommentsForm(forms.ModelForm):
    """The only change allowed on a published post: turning comments off."""

    class Meta:
        model = Post
        fields = ["comments_enabled"]

    def clean_comments_enabled(self):
        enabled = self.cleaned_data["comments_enabled"]
        if enabled and not self.instance.comments_enabled:
            raise forms.ValidationError(_("Chop etilgan post uchun izohlarni faqat o'chirish mumkin."))
        return enabled


class GeneratorForm(forms.Form):
    language = forms.ChoiceField(label=_("Til"), choices=settings.LANGUAGES, initial="uz")


class PromotionGeneratorForm(GeneratorForm):
    city = forms.ModelChoiceField(
        label=_("Shahar"), queryset=City.objects.all(), required=False, empty_label=_("Barcha shaharlar")
    )
    store = forms.ModelChoiceField(
        label=_("yoki do'kon"), queryset=Store.objects.active().select_related("city"), required=False
    )


class PriceGeneratorForm(GeneratorForm):
    product = forms.ModelChoiceField(
        label=_("Mahsulot"), queryset=Product.objects.all(), widget=forms.Select(attrs={"data-tom-select": "product"})
    )
    city = forms.ModelChoiceField(
        label=_("Shahar"), queryset=City.objects.all(), required=False, empty_label=_("Barcha shaharlar")
    )


class BasketGeneratorForm(GeneratorForm):
    basket = forms.ModelChoiceField(label=_("Savat"), queryset=Basket.objects.all())
    city = forms.ModelChoiceField(
        label=_("Shahar"), queryset=City.objects.all(), required=False, empty_label=_("Barcha shaharlar")
    )


class NewStoreGeneratorForm(GeneratorForm):
    store = forms.ModelChoiceField(
        label=_("Yangi do'kon"), queryset=Store.objects.filter(is_new=True).select_related("city")
    )
