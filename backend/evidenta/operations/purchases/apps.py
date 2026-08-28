from django.apps import AppConfig


class PurchasesConfig(AppConfig):
    name = "evidenta.operations.purchases"
    label = "purchases"
    verbose_name = "Purchase documents"

    def ready(self) -> None:
        from evidenta.operations.purchases.types import register_purchase_types

        register_purchase_types()
