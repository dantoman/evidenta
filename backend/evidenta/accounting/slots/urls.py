"""Role binding routes -- `/api/v1/accounting/slots/`.

The role is a path segment because it is a key of a closed catalogue, not a row
somebody created: `role-bindings/CASA_MDL` names the same thing in every company,
and a typo in it is refused by the service with `slots.role_unknown`.
"""

from django.urls import path

from evidenta.accounting.slots import views

app_name = "slots"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/role-bindings",
        views.RoleBindingListView.as_view(),
        name="role-bindings",
    ),
    path(
        "companies/<uuid:company_id>/role-bindings/<str:role>",
        views.RoleBindingView.as_view(),
        name="role-binding",
    ),
]
