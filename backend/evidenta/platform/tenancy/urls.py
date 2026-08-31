"""Tenancy routes.

The tenant never appears in a path (C8) -- it comes from the subdomain. A company
does, because it is a resource inside the tenant, and the screens that work on one
have to be able to say which.
"""

from django.urls import path

from evidenta.platform.tenancy import views

app_name = "tenancy"

urlpatterns = [
    path("companies", views.CompanyListView.as_view(), name="companies"),
    path(
        "companies/<uuid:company_id>",
        views.CompanyDetailView.as_view(),
        name="company",
    ),
    # Closing is a sub-resource, not a field: it carries a reason and its own
    # permission key (ADR-083).
    path(
        "companies/<uuid:company_id>/close",
        views.CompanyCloseView.as_view(),
        name="company-close",
    ),
    # The workspace has no identifier in the path for the same reason: it is the
    # host the browser is already on.
    path("workspace", views.WorkspaceView.as_view(), name="workspace"),
]
