"""`/api/v1/support/` -- the client's side of a support grant (ADR-077)."""

from django.urls import path

from evidenta.platform.support import views

app_name = "support"

urlpatterns = [
    path("grants", views.GrantsView.as_view(), name="grants"),
    path("grants/<uuid:grant_id>/approve", views.ApproveView.as_view(), name="approve"),
    path("grants/<uuid:grant_id>/revoke", views.RevokeView.as_view(), name="revoke"),
    path("session", views.SessionView.as_view(), name="session"),
]
