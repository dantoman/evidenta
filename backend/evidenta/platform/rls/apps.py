"""App configuration for the RLS platform module.

This app holds no models. It exists so the query guard is installed once, at
startup, for every entry point -- request, task, management command, shell --
rather than by each of them remembering to.
"""

from django.apps import AppConfig


class RlsConfig(AppConfig):
    name = "evidenta.platform.rls"
    label = "rls"
    verbose_name = "Row Level Security"

    def ready(self) -> None:
        from evidenta.platform.rls.guard import install

        install()
