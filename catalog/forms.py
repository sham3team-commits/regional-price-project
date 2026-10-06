from django import forms
from django.utils.translation import gettext_lazy as _

from locations.models import Store

from .models import Category, Price, Product

MAX_PHOTO_BYTES = 10 * 1024 * 1024


def validate_photo_size(photo):
    if photo and getattr(photo, "size", 0) > MAX_PHOTO_BYTES:
        raise forms.ValidationError(_("Rasm hajmi 10 MB dan oshmasligi kerak."))
    return photo


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "name_ru", "category", "unit", "brand", "description", "photo"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def clean_photo(self):
        return validate_photo_size(self.cleaned_data.get("photo"))


class PriceForm(forms.ModelForm):
    """Fast price entry. Validation rules live in Price.clean(), which ModelForm calls."""

    class Meta:
        model = Price
        fields = ["product", "store", "price", "is_promo", "old_price", "promo_starts", "promo_ends", "recorded_on"]
        widgets = {
            "product": forms.Select(attrs={"autofocus": True, "data-tom-select": "product"}),
            "store": forms.Select(attrs={"data-tom-select": "store"}),
            "price": forms.NumberInput(attrs={"inputmode": "numeric", "min": 1}),
            "old_price": forms.NumberInput(attrs={"inputmode": "numeric", "min": 1}),
            "promo_starts": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "promo_ends": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "recorded_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["store"].queryset = Store.objects.active().select_related("city")


class ProductFilterForm(forms.Form):
    q = forms.CharField(label=_("Qidiruv"), required=False)
    category = forms.ModelChoiceField(label=_("Kategoriya"), queryset=Category.objects.all(), required=False)
