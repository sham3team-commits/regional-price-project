from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView

from catalog.models import Price, Product
from catalog.services import price_change_alerts
from locations.models import Store
from posts.models import Post

from .mixins import StaffRequiredMixin


def healthz(request):
    """Used by the Docker healthcheck: the app is up and the database answers."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())
        week_start = timezone.make_aware(datetime.combine(monday, time.min))
        return super().get_context_data(
            product_count=Product.objects.count(),
            store_count=Store.objects.active().count(),
            prices_this_week=Price.objects.filter(created_at__gte=week_start).count(),
            upcoming_posts=Post.objects.filter(status=Post.Status.SCHEDULED)
            .select_related("rubric")
            .order_by("scheduled_at")[:10],
            failed_posts=Post.objects.filter(status=Post.Status.FAILED)
            .select_related("rubric")
            .order_by("-updated_at")[:10],
            alerts=price_change_alerts(settings.PRICE_ALERT_PERCENT)[:15],
            alert_percent=settings.PRICE_ALERT_PERCENT,
            **kwargs,
        )
