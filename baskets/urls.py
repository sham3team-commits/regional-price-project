from django.urls import path

from . import views

app_name = "baskets"

urlpatterns = [
    path("", views.BasketListView.as_view(), name="basket_list"),
    path("new/", views.BasketEditView.as_view(), name="basket_create"),
    path("<int:pk>/edit/", views.BasketEditView.as_view(), name="basket_update"),
    path("<int:pk>/", views.BasketCompareView.as_view(), name="basket_compare"),
]
