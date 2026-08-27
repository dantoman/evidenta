"""Partner routes -- `/api/v1/masterdata/partners/`.

No company segment: a partner belongs to the tenant. Which accounts a particular
company posts it to is `CompanyPartner`, and that has no surface yet because
nothing at F1 reads it.
"""

from django.urls import path

from evidenta.masterdata.partners import views

app_name = "partners"

urlpatterns = [
    path("", views.PartnerListView.as_view(), name="partners"),
    path("<uuid:partner_id>", views.PartnerDetailView.as_view(), name="partner"),
    path(
        "<uuid:partner_id>/activation",
        views.PartnerActivationView.as_view(),
        name="partner-activation",
    ),
]
