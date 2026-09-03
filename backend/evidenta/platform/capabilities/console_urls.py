"""`/api/v1/platform/capabilities/` -- served only on the console host (ADR-076)."""

from django.urls import path

from evidenta.platform.capabilities import console_views

app_name = "platform_capabilities"

urlpatterns = [
    path("", console_views.CapabilitiesView.as_view(), name="capabilities"),
]
