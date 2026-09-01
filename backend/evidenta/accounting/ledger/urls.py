"""Ledger routes -- `/api/v1/accounting/ledger/`.

The company is a path segment because a balance belongs to a company; the tenant
never appears, because it comes from the subdomain (C8).
"""

from django.urls import path

from evidenta.accounting.ledger import views

app_name = "ledger"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/entries",
        views.EntryListView.as_view(),
        name="entries",
    ),
    # The panel of the company, for the month the caller's day falls in. Under
    # the ledger because that is where every figure on it comes from -- and the
    # ones that cannot come from anywhere are refused by the service rather than
    # answered as zeros.
    path(
        "companies/<uuid:company_id>/overview",
        views.CompanyOverviewView.as_view(),
        name="overview",
    ),
    path(
        "companies/<uuid:company_id>/trial-balance",
        views.TrialBalanceView.as_view(),
        name="trial-balance",
    ),
    # F1.8. The account is a path segment because the ledger is *of* it; the
    # window is a query, because it is a choice the reader makes each time.
    path(
        "companies/<uuid:company_id>/accounts/<uuid:account_id>/ledger",
        views.AccountLedgerView.as_view(),
        name="account-ledger",
    ),
    path(
        "companies/<uuid:company_id>/accounts/<uuid:account_id>/general-ledger",
        views.GeneralLedgerView.as_view(),
        name="general-ledger",
    ),
    # The family is named by the module that owns it -- `sales`, `purchases`,
    # `treasury` -- and the registry answers which types that is. A route naming
    # type codes would put another module's vocabulary in this one's addresses.
    path(
        "companies/<uuid:company_id>/journals/<slug:owner>",
        views.DocumentJournalView.as_view(),
        name="document-journal",
    ),
    path(
        "companies/<uuid:company_id>/correspondence",
        views.CorrespondenceView.as_view(),
        name="correspondence",
    ),
    # No company segment: the entry's id is the whole address, and RLS decides
    # whether this context may read it -- the same shape as the reversal route.
    path("entries/<uuid:entry_id>", views.EntryDetailView.as_view(), name="entry-detail"),
]
