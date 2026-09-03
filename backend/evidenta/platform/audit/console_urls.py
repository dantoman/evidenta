"""`/api/v1/platform/privileged-log/` -- served only on the console host (ADR-076)."""

from django.urls import path

from evidenta.platform.audit import console_views

app_name = "platform_audit"

urlpatterns = [
    path("", console_views.PrivilegedLogView.as_view(), name="privileged-log"),
]
