"""Settlement routes -- `/api/v1/settlements/`.

The open items are a company's; the allocation names two documents and needs no
company in the path, because both carry one and the service refuses a pair that
does not agree. The tenant never appears (`C8`).
"""

from django.urls import path

from evidenta.operations.settlements import views

app_name = "settlements"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/open",
        views.OpenItemsView.as_view(),
        name="open-items",
    ),
    path("allocations", views.AllocationView.as_view(), name="allocations"),
]
