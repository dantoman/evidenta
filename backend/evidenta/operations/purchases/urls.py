"""Purchase routes -- `/api/v1/purchases/`.

The company is a path segment on the collection because an invoice is recorded
*in* one; the document's own id addresses it afterwards, and RLS decides whether
this context may read it. The tenant never appears (`C8`).

`recording` is the noun the sales side spells `issuance`, and the difference is
the domain's: we issue our invoices and we record theirs.
"""

from django.urls import path

from evidenta.operations.purchases import views

app_name = "purchases"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/invoices",
        views.PurchaseListView.as_view(),
        name="invoices",
    ),
    path("invoices/<uuid:document_id>", views.PurchaseDetailView.as_view(), name="invoice"),
    path(
        "invoices/<uuid:document_id>/lines",
        views.PurchaseLinesView.as_view(),
        name="invoice-lines",
    ),
    path(
        "invoices/<uuid:document_id>/recording",
        views.PurchaseRecordingView.as_view(),
        name="invoice-recording",
    ),
]
