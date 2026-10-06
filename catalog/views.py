from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView, View

from core.mixins import StaffRequiredMixin
from core.templatetags.formatting import som

from .forms import PriceForm, ProductFilterForm, ProductForm
from .models import Price, Product
from .services import current_prices, price_history_chart

STORE_SESSION_KEY = "price_entry_store"


class ProductListView(StaffRequiredMixin, ListView):
    template_name = "catalog/product_list.html"
    paginate_by = 25

    def get_queryset(self):
        self.filter_form = ProductFilterForm(self.request.GET or None)
        products = Product.objects.select_related("category")
        if self.filter_form.is_valid():
            query = self.filter_form.cleaned_data["q"].strip()
            category = self.filter_form.cleaned_data["category"]
            if query:
                products = products.filter(
                    Q(name__icontains=query) | Q(name_ru__icontains=query) | Q(brand__icontains=query)
                )
            if category:
                products = products.filter(category=category)
        return products

    def get_context_data(self, **kwargs):
        params = self.request.GET.copy()
        params.pop("page", None)
        return super().get_context_data(filter_form=self.filter_form, querystring=params.urlencode(), **kwargs)


class ProductDetailView(StaffRequiredMixin, DetailView):
    model = Product
    template_name = "catalog/product_detail.html"

    def get_context_data(self, **kwargs):
        product = self.object
        return super().get_context_data(
            current=current_prices(product),
            history=product.prices.select_related("store__city")[:100],
            chart=price_history_chart(product),
            **kwargs,
        )


class ProductFormMixin(StaffRequiredMixin, SuccessMessageMixin):
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"
    success_message = gettext_lazy("Mahsulot saqlandi.")

    def get_success_url(self):
        return reverse("catalog:product_detail", args=[self.object.pk])


class ProductCreateView(ProductFormMixin, CreateView):
    pass


class ProductUpdateView(ProductFormMixin, UpdateView):
    pass


class PriceEntryView(StaffRequiredMixin, FormView):
    """Fast data entry: the store stays selected between entries, the form comes back empty."""

    form_class = PriceForm
    template_name = "catalog/price_entry.html"

    def get_initial(self):
        return {"store": self.request.session.get(STORE_SESSION_KEY), "product": self.request.GET.get("product")}

    def form_valid(self, form):
        price = form.save()
        self.request.session[STORE_SESSION_KEY] = price.store_id
        messages.success(
            self.request,
            _("Saqlandi: %(product)s — %(store)s — %(price)s so'm")
            % {"product": price.product.name, "store": price.store.name, "price": som(price.price)},
        )
        return redirect("catalog:price_entry")

    def get_context_data(self, **kwargs):
        today_entries = (
            Price.objects.filter(created_at__date=timezone.localdate())
            .select_related("product", "store__city")
            .order_by("-created_at")[:50]
        )
        return super().get_context_data(today_entries=today_entries, **kwargs)


class LastPriceView(StaffRequiredMixin, View):
    """JSON for the price entry page: the previous price of a product in a store."""

    def get(self, request):
        product_id = request.GET.get("product", "")
        store_id = request.GET.get("store", "")
        if not (product_id.isdigit() and store_id.isdigit()):
            return JsonResponse({"found": False})
        last = (
            Price.objects.filter(product_id=product_id, store_id=store_id)
            .order_by("-recorded_on", "-created_at", "-pk")
            .first()
        )
        if last is None:
            return JsonResponse({"found": False})
        return JsonResponse(
            {
                "found": True,
                "price": last.current_value(),
                "date": last.recorded_on.strftime("%d.%m.%Y"),
                "is_promo": last.promo_active(),
            }
        )
