"""Strict-form routes -- `/api/v1/strict-forms/`.

The company is in the path because a range is issued to a company (`C8`). There
is deliberately no route that issues a number: that happens at posting, inside
the document's transaction.
"""

from django.urls import path

from evidenta.platform.strictforms import views

app_name = "strictforms"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/allocations",
        views.AllocationListView.as_view(),
        name="allocations",
    ),
    path(
        "companies/<uuid:company_id>/allocations/<uuid:allocation_id>",
        views.AllocationDetailView.as_view(),
        name="allocation",
    ),
    path(
        "companies/<uuid:company_id>/allocations/<uuid:allocation_id>/withdrawal",
        views.WithdrawalView.as_view(),
        name="allocation-withdrawal",
    ),
    path("companies/<uuid:company_id>/voids", views.VoidView.as_view(), name="voids"),
]
