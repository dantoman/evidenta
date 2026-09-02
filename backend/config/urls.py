"""Root URL configuration.

Versioning lives in the path (C7): every resource sits under /api/v1/ and follows
its module -- /api/v1/accounting/, /api/v1/payroll/. Only authentication is routed
so far; the API conventions themselves are F0.10.1.

The tenant comes from the subdomain, never from the path or the payload (C8), so
no URL here will ever carry a tenant identifier.
"""

from django.urls import URLPattern, URLResolver, include, path

from config import health

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v1/auth/", include("evidenta.platform.identity.urls")),
    path("api/v1/accounting/coa/", include("evidenta.accounting.coa.urls")),
    path("api/v1/accounting/periods/", include("evidenta.accounting.periods.urls")),
    path("api/v1/accounting/entries/", include("evidenta.accounting.posting.urls")),
    path("api/v1/accounting/ledger/", include("evidenta.accounting.ledger.urls")),
    path(
        "api/v1/accounting/opening-balances/",
        include("evidenta.accounting.opening.urls"),
    ),
    path("api/v1/masterdata/partners/", include("evidenta.masterdata.partners.urls")),
    path("api/v1/fiscal/", include("evidenta.fiscal.parameters.urls")),
    path("api/v1/sales/", include("evidenta.operations.sales.urls")),
    path("api/v1/purchases/", include("evidenta.operations.purchases.urls")),
    path("api/v1/treasury/", include("evidenta.operations.treasury.urls")),
    path("api/v1/settlements/", include("evidenta.operations.settlements.urls")),
    path("api/v1/payroll/", include("evidenta.operations.payroll.urls")),
    path("api/v1/tax/", include("evidenta.operations.tax.urls")),
    path("api/v1/strict-forms/", include("evidenta.platform.strictforms.urls")),
    path("api/v1/", include("evidenta.platform.tenancy.urls")),
    # Operational, not API. They sit outside /api/v1/ because they are not
    # resources and are not versioned with the product: an orchestrator probe
    # must not have to be updated when the API version changes.
    path("healthz", health.live),
    path("readyz", health.ready),
]
