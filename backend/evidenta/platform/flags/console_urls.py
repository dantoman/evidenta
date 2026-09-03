"""`/api/v1/platform/flags/` -- served only on the console host (ADR-076)."""

from django.urls import path

from evidenta.platform.flags import console_views

app_name = "platform_flags"

urlpatterns = [
    path("", console_views.FlagsView.as_view(), name="flags"),
]
