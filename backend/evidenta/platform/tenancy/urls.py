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
]
