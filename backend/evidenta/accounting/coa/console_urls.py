"""`/api/v1/platform/coa-templates/` -- served only on the console host (ADR-076)."""

from django.urls import path

from evidenta.accounting.coa import console_views

app_name = "platform_coa"

urlpatterns = [
    path("", console_views.CoaTemplatesView.as_view(), name="coa-templates"),
]
