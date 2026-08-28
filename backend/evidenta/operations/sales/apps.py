from django.apps import AppConfig


class SalesConfig(AppConfig):
    """The sales-side document types, registered with the document core.

    The core never lists them: `operations` calls `documents.register(...)`, so
    `platform` does not import anything above it and a type nobody registered
    cannot be created at all. The same inversion the accounting event vocabulary
    uses (ADR-038), for the same reason.
    """

    name = "evidenta.operations.sales"
    label = "sales"
    verbose_name = "Sales documents"

    def ready(self) -> None:
        from evidenta.operations.sales.types import register_sales_types

        register_sales_types()
