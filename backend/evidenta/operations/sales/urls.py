"""Sales routes -- `/api/v1/sales/`.

The company is a path segment on the collection because an invoice is *of* one;
the document's own id addresses it afterwards, and RLS decides whether this
context may read it. The tenant never appears (`C8`).

`issuance` is a noun: it is the thing being created -- the invoice becoming issued
and posted -- so the POST reads like every other POST here.
"""

from django.urls import path

from evidenta.operations.sales import views

app_name = "sales"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/invoices",
        views.SalesListView.as_view(),
        name="invoices",
    ),
    path("invoices/<uuid:document_id>", views.SalesDetailView.as_view(), name="invoice"),
    path("invoices/<uuid:document_id>/lines", views.SalesLinesView.as_view(), name="invoice-lines"),
    path(
        "invoices/<uuid:document_id>/issuance",
        views.SalesIssuanceView.as_view(),
        name="invoice-issuance",
    ),
]
