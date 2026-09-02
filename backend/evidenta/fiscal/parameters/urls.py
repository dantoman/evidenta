"""Fiscal routes -- `/api/v1/fiscal/`.

Read-only. Values enter `fiscal_parameter` through the privileged loader
(ADR-049), never through HTTP; what is served here is what a document screen
needs to *read* before it can state a regime.
"""

from django.urls import path

from evidenta.fiscal.parameters import views

app_name = "fiscal"

urlpatterns = [
    path("vat/regimes", views.VatRegimesView.as_view(), name="vat-regimes"),
]
