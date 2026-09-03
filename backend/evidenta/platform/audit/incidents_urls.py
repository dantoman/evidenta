"""`/api/v1/platform/incidents/` -- served only on the console host (ADR-076)."""

from django.urls import path

from evidenta.platform.audit import incidents_views

app_name = "platform_incidents"

urlpatterns = [
    path("", incidents_views.IncidentsView.as_view(), name="incidents"),
]
