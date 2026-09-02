"""Statutory return routes -- `/api/v1/tax/`.

The company is a path segment on the collection because a return is *of* a
company; a version's own id addresses it after that, and RLS decides whether this
context may read it.

`ipc` is in the path because the unified monthly return is one of several this
module will carry, not because the form's name is part of the API. When the VAT
return arrives it gets its own segment beside this one.
"""

from django.urls import path

from evidenta.operations.tax import views

app_name = "tax"

urlpatterns = [
    path(
        "ipc/companies/<uuid:company_id>",
        views.IpcListView.as_view(),
        name="ipc-declarations",
    ),
    path("ipc/<uuid:declaration_id>", views.IpcDetailView.as_view(), name="ipc-declaration"),
    # A noun, not a verb: the correction is the version being created, and the
    # POST that creates one reads like every other POST here.
    path(
        "ipc/<uuid:declaration_id>/correction",
        views.IpcCorrectionView.as_view(),
        name="ipc-correction",
    ),
    path(
        "ipc/<uuid:declaration_id>/submission",
        views.IpcSubmissionView.as_view(),
        name="ipc-submission",
    ),
    # `T1` as a reading. The screen shows it before anybody files.
    path(
        "ipc/<uuid:declaration_id>/reconciliation",
        views.IpcReconciliationView.as_view(),
        name="ipc-reconciliation",
    ),
    # The VAT segment, beside IPC as promised above. The side is a path segment
    # because the two registers are two documents, not one with a filter.
    path(
        "vat/companies/<uuid:company_id>/registers/<slug:side>",
        views.VatRegisterView.as_view(),
        name="vat-register",
    ),
]
