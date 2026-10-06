from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.generic import DetailView, ListView, View

from core.mixins import StaffRequiredMixin

from .forms import BasketForm, BasketItemFormSet, CityFilterForm
from .models import Basket
from .services import compare_basket


class BasketListView(StaffRequiredMixin, ListView):
    template_name = "baskets/basket_list.html"
    queryset = Basket.objects.annotate(item_count=Count("items"))


class BasketEditView(StaffRequiredMixin, View):
    """Create or edit a basket together with its items (inline formset)."""

    template_name = "baskets/basket_form.html"

    def get_object(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(Basket, pk=pk) if pk else Basket()

    def get(self, request, *args, **kwargs):
        basket = self.get_object()
        return self._render(BasketForm(instance=basket), BasketItemFormSet(instance=basket))

    def post(self, request, *args, **kwargs):
        basket = self.get_object()
        form = BasketForm(request.POST, instance=basket)
        formset = BasketItemFormSet(request.POST, instance=basket)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                basket = form.save()
                formset.instance = basket
                formset.save()
            messages.success(request, _("Savat saqlandi."))
            return redirect("baskets:basket_compare", pk=basket.pk)
        return self._render(form, formset)

    def _render(self, form, formset):
        return render(self.request, self.template_name, {"form": form, "formset": formset, "basket": form.instance})


class BasketCompareView(StaffRequiredMixin, DetailView):
    model = Basket
    template_name = "baskets/basket_compare.html"

    def get_context_data(self, **kwargs):
        filter_form = CityFilterForm(self.request.GET or None)
        city = filter_form.cleaned_data["city"] if filter_form.is_valid() else None
        return super().get_context_data(
            filter_form=filter_form,
            city=city,
            items=self.object.items.select_related("product"),
            results=compare_basket(self.object, city),
            **kwargs,
        )
