from django.apps import AppConfig


class SettlementsConfig(AppConfig):
    name = "evidenta.operations.settlements"
    label = "settlements"
    verbose_name = "Settlements"

    def ready(self) -> None:
        # The revaluation asks "what is open in foreign currency" through a
        # registry (`accounting.currency.services.monetary_items`), because the
        # graph runs one way and `accounting` cannot import this module. The
        # registration is the inversion that keeps `D2` intact -- the same
        # shape as the handler registry of ADR-038. Once per interpreter.
        from evidenta.accounting.currency.services.monetary_items import register_provider
        from evidenta.operations.settlements.services.monetary import open_currency_items

        register_provider("settlements", open_currency_items)
