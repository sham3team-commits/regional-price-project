from django import forms

from .models import Store


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ["name", "city", "address", "map_url", "latitude", "longitude", "opened_on", "is_new", "is_active"]
        widgets = {"opened_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
