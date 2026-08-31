from django.apps import AppConfig


class TreasuryConfig(AppConfig):
    name = "evidenta.operations.treasury"
    label = "treasury"
    verbose_name = "Treasury documents"

    def ready(self) -> None:
        from evidenta.operations.treasury.types import register_treasury_types

        register_treasury_types()
