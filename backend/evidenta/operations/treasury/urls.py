"""Treasury routes -- `/api/v1/treasury/`.

One collection for both directions; the movement's own id addresses it
afterwards. The tenant never appears (`C8`).
"""

from django.urls import path

from evidenta.operations.treasury import views

app_name = "treasury"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/movements",
        views.TreasuryListView.as_view(),
        name="movements",
    ),
    path("movements/<uuid:document_id>", views.TreasuryDetailView.as_view(), name="movement"),
    path(
        "movements/<uuid:document_id>/recording",
        views.TreasuryRecordingView.as_view(),
        name="movement-recording",
    ),
]
