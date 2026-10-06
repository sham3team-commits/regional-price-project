from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from locations.models import City

from .models import Basket, BasketItem


class BasketForm(forms.ModelForm):
    class Meta:
        model = Basket
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


BasketItemFormSet = inlineformset_factory(
    Basket,
    BasketItem,
    fields=["product", "quantity"],
    extra=1,
    can_delete=True,
    widgets={
        "product": forms.Select(attrs={"data-tom-select": "product"}),
        "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
    },
)


class CityFilterForm(forms.Form):
    city = forms.ModelChoiceField(
        label=_("Shahar"), queryset=City.objects.all(), required=False, empty_label=_("Barcha shaharlar")
    )
