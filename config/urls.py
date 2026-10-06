from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from core.views import DashboardView, healthz

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("healthz/", healthz, name="healthz"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("", include("catalog.urls")),
    path("stores/", include("locations.urls")),
    path("baskets/", include("baskets.urls")),
    path("posts/", include("posts.urls")),
    # Single-operator internal tool: uploaded media is served by Django itself.
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
