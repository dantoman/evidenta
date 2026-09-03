"""`/api/v1/platform/spaces/` -- served only on the console host (ADR-076)."""

from django.urls import path

from evidenta.platform.tenancy import console_views

app_name = "platform_spaces"

urlpatterns = [
    path("", console_views.SpacesView.as_view(), name="spaces"),
]
