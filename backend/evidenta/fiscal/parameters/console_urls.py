"""The console's fiscal routes -- `/api/v1/platform/fiscal-parameters/` (ADR-076).

Mounted from `config/urls.py` under the platform prefix, and served only on the
`admin.` host: the tenant resolver refuses the prefix everywhere else. Kept apart
from `urls.py` because the two answer different people -- `vat/regimes` is what
a document screen reads on a tenant's host, this is what an operator writes.
"""

from django.urls import path

from evidenta.fiscal.parameters import console_views

app_name = "fiscal_console"

urlpatterns = [
    path("", console_views.FiscalParametersView.as_view(), name="parameters"),
    path(
        "<uuid:parameter_id>/activate",
        console_views.ActivateFiscalParameterView.as_view(),
        name="activate",
    ),
]
