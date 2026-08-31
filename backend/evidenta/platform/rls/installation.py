"""Pointing this process's default connection at the installation role.

Two operator commands need it, for the same reason: every policy on ``tenant``,
``user``, ``membership`` and ``role`` is written ``TO evidenta_app``, and under
``FORCE ROW LEVEL SECURITY`` the owner therefore has **no applicable policy at
all** -- it is refused, not waved through. Creating the first tenant and
repairing a tenant's system roles are both DBA acts, spelled that way.

It lives here, once, because the rebinding has a subtlety that was measured
rather than reasoned: there are **two** copies of the connection settings, and
rebinding only the first reconnects as the same role it was already using.

Nothing but an operator command may call this. It is not a privileged path in the
`P-*` sense -- it adds no route, grants nothing to the application role, and
changes no product surface.
"""

from __future__ import annotations

from django.conf import settings
from django.db import connections


class InstallationRoleError(RuntimeError):
    """The installation connection is not configured."""


def bind_default_to_installation_role() -> None:
    admin = settings.DATABASES.get("admin")
    if not admin:
        raise InstallationRoleError(
            "conexiunea de instalare nu este configurată: setați DB_ADMIN_USER și "
            "DB_ADMIN_PASSWORD. Rolurile de sistem nu se pot scrie sub rolul aplicației "
            "și nici sub cel de proprietar -- politicile sunt scrise `TO evidenta_app`."
        )

    # Both halves, and the second is the one that matters: the handler's
    # `databases` dict is what a *new* wrapper would be built from, while the
    # existing wrapper holds its own copy in `settings_dict`.
    connections["default"].close()
    rebound = {
        **connections.databases["default"],
        "USER": admin["USER"],
        "PASSWORD": admin["PASSWORD"],
    }
    connections.databases["default"] = rebound
    connections["default"].settings_dict.update(rebound)
