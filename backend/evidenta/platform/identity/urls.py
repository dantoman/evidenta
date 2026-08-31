"""Authentication routes.

``/api/v1/auth/login`` is named in ``TENANT_CONTEXT_EXEMPT_PATHS``; the other two
are not, and must not be. Keeping the exempt path as an exact string rather than
a prefix is what makes that distinction hold: a prefix would have exempted every
route added under ``/auth/`` later, including ones that read data.
"""

from django.urls import path

from evidenta.platform.identity import views

app_name = "identity"

urlpatterns = [
    path("login", views.login, name="login"),
    path("logout", views.logout, name="logout"),
    path("whoami", views.whoami, name="whoami"),
    # Editarea propriului nume. Nu poartă identificator: schimbă utilizatorul
    # din sesiune și pe nimeni altcineva.
    path("profile", views.profile, name="profile"),
]
