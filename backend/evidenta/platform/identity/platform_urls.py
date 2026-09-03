"""The console's routes about people -- `/api/v1/platform/staff/`.

Separate from `urls.py` because the two are mounted at different prefixes and
served on different hosts: `/api/v1/auth/` answers on every host, this answers
only on `admin.` (ADR-076 §4.2) -- the tenant resolver refuses the prefix
everywhere else before a view runs, see `CONSOLE_PATH_PREFIXES`.
"""

from django.urls import path

from evidenta.platform.identity import console_views, views

app_name = "platform_staff"

urlpatterns = [
    path("me", views.staff_me, name="me"),
    path("", console_views.StaffView.as_view(), name="staff"),
    path("<uuid:user_id>/revoke", console_views.RevokeStaffView.as_view(), name="revoke"),
]
