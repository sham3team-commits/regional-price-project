from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, ListView, UpdateView

from core.mixins import StaffRequiredMixin

from .forms import StoreForm
from .models import City, Store


class StoreListView(StaffRequiredMixin, ListView):
    template_name = "locations/store_list.html"
    paginate_by = 50

    def get_queryset(self):
        stores = Store.objects.select_related("city")
        self.city_id = self.request.GET.get("city", "")
        if self.city_id.isdigit():
            stores = stores.filter(city_id=self.city_id)
        return stores

    def get_context_data(self, **kwargs):
        querystring = f"city={self.city_id}" if self.city_id.isdigit() else ""
        return super().get_context_data(
            cities=City.objects.all(), selected_city=self.city_id, querystring=querystring, **kwargs
        )


class StoreFormMixin(StaffRequiredMixin, SuccessMessageMixin):
    model = Store
    form_class = StoreForm
    template_name = "locations/store_form.html"
    success_url = reverse_lazy("locations:store_list")
    success_message = _("Do'kon saqlandi.")


class StoreCreateView(StoreFormMixin, CreateView):
    pass


class StoreUpdateView(StoreFormMixin, UpdateView):
    pass
