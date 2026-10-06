from django.urls import path

from . import views

app_name = "locations"

urlpatterns = [
    path("", views.StoreListView.as_view(), name="store_list"),
    path("new/", views.StoreCreateView.as_view(), name="store_create"),
    path("<int:pk>/edit/", views.StoreUpdateView.as_view(), name="store_update"),
]
