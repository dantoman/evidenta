"""Currency routes -- `/api/v1/accounting/currency/`.

The rate is global and takes no company; the revaluation is a company's, so the
company is a path segment. The tenant never appears (`C8`).
"""

from django.urls import path

from evidenta.accounting.currency import views

app_name = "currency"

urlpatterns = [
    path("rates", views.RateView.as_view(), name="rates"),
    path(
        "companies/<uuid:company_id>/revaluations",
        views.RevaluationListView.as_view(),
        name="revaluations",
    ),
]
