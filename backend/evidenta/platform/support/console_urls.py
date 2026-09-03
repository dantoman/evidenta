"""`/api/v1/platform/support-grants/` -- served only on the console host (ADR-076)."""

from django.urls import path

from evidenta.platform.support import console_views

app_name = "platform_support"

urlpatterns = [
    path("", console_views.ConsoleGrantsView.as_view(), name="grants"),
]
