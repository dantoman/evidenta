"""Routes for the chart of accounts.

No trailing slashes, following the authentication routes: one shape for the whole
API, chosen once. The company appears as a path segment because an account
belongs to a company; the tenant never appears, because it comes from the
subdomain (C8).
"""

from django.urls import path

from evidenta.accounting.coa import views

app_name = "coa"

urlpatterns = [
    path("templates", views.TemplateListView.as_view(), name="templates"),
    path(
        "companies/<uuid:company_id>/chart",
        views.ChartView.as_view(),
        name="chart",
    ),
    path(
        "companies/<uuid:company_id>/accounts",
        views.AccountListView.as_view(),
        name="accounts",
    ),
    path("accounts/<uuid:account_id>", views.AccountDetailView.as_view(), name="account"),
]
