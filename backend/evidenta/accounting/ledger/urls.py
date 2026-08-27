"""Ledger routes -- `/api/v1/accounting/ledger/`.

The company is a path segment because a balance belongs to a company; the tenant
never appears, because it comes from the subdomain (C8).
"""

from django.urls import path

from evidenta.accounting.ledger import views

app_name = "ledger"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/trial-balance",
        views.TrialBalanceView.as_view(),
        name="trial-balance",
    ),
]
