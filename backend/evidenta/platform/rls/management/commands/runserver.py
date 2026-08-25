"""``runserver``, with its startup migration check declared unguarded.

Django reads ``django_migrations`` before it binds the port, on the default
connection -- the application one. The query guard refuses that read, and it is
right to: nothing has set a tenant context, and the guard cannot tell a startup
check apart from a request that forgot one.

So the exemption is stated here, narrowly, instead of being carved into the
guard. The guard keeps refusing every context-less query on the application
connection; this command declares the single query it makes before serving
anything. Widening the guard instead would have exempted the check for every
caller, including the ones that are actually bugs.
"""

from __future__ import annotations

from typing import Any

from django.core.management.commands.runserver import Command as RunserverCommand

from evidenta.platform.rls.context import unguarded


class Command(RunserverCommand):
    def check_migrations(self, *args: Any, **kwargs: Any) -> None:
        with unguarded("runserver: migration check before binding the port"):
            super().check_migrations(*args, **kwargs)
