"""Root URL configuration.

Versioning lives in the path (C7): every resource sits under /api/v1/ and follows
its module -- /api/v1/accounting/, /api/v1/payroll/. Nothing is routed yet; the
API conventions themselves are F0.10.1.

The tenant comes from the subdomain, never from the path or the payload (C8), so
no URL here will ever carry a tenant identifier.
"""

from django.urls import URLPattern, URLResolver

urlpatterns: list[URLPattern | URLResolver] = []
