"""Period routes -- `/api/v1/accounting/periods/`."""

from django.urls import path

from evidenta.accounting.periods import views

app_name = "periods"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/fiscal-years",
        views.FiscalYearView.as_view(),
        name="fiscal-years",
    ),
    path(
        "companies/<uuid:company_id>/vat-periods",
        views.VatPeriodView.as_view(),
        name="vat-periods",
    ),
]
