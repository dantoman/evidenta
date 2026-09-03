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
    # The closing door (G1). The months of one exercise hang off the company and
    # the exercise, because that is what they are of; a period's own id addresses
    # it afterwards, and the policy decides whether this context may see it. The
    # nouns are what is being created -- a closing, a reopening -- so the POSTs
    # read like every other POST here.
    path(
        "companies/<uuid:company_id>/fiscal-years/<uuid:year_id>/periods",
        views.PeriodListView.as_view(),
        name="periods",
    ),
    path(
        "periods/<uuid:period_id>/closing-checks",
        views.ClosingChecksView.as_view(),
        name="closing-checks",
    ),
    path(
        "periods/<uuid:period_id>/closing",
        views.PeriodClosingView.as_view(),
        name="period-closing",
    ),
    path(
        "periods/<uuid:period_id>/reopening",
        views.PeriodReopeningView.as_view(),
        name="period-reopening",
    ),
    path(
        "fiscal-years/<uuid:year_id>/closing",
        views.FiscalYearClosingView.as_view(),
        name="fiscal-year-closing",
    ),
]
